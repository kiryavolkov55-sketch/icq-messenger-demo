package main

import (
	cryptorand "crypto/rand"
	"database/sql"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"math/rand"
	"mime"
	"net/http"
	"os"
	"path/filepath"
	"regexp"  
	"strings"
	"sync"
	"time"
	"unicode"

	"github.com/gorilla/websocket"
	_ "modernc.org/sqlite"
)

const maxUploadedFileSize = 5 * 1024 * 1024
var emailRegex = regexp.MustCompile(`^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$`)

func init() {
	rand.Seed(time.Now().UnixNano())
}

type User struct {
	UIN      int    `json:"uin"`
	Name     string `json:"name"`
	Password string `json:"password"`
	Email    string `json:"email"`
	Phone    string `json:"phone"`
	Avatar   string `json:"avatar"`
}

type Contact struct {
	UIN    int    `json:"uin"`
	Name   string `json:"name"`
	Status string `json:"status"`
	Group  string `json:"group"`
	Avatar string `json:"avatar"`
}

type Message struct {
	From      int    `json:"from"`
	To        int    `json:"to"`
	Text      string `json:"text"`
	Timestamp string `json:"timestamp"`
	GroupID   *int   `json:"group_id,omitempty"`
}

type Client struct {
	uin  int
	name string
	conn *websocket.Conn
}

var (
	db      *sql.DB
	clients = make(map[int]*Client)
	mu      sync.RWMutex
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

func initDB() {
	var err error
	db, err = sql.Open("sqlite", "./icq.db")
	if err != nil {
		log.Fatal("Ошибка открытия БД:", err)
	}
	db.SetMaxOpenConns(1)

	_, err = db.Exec(`CREATE TABLE IF NOT EXISTS users (
		uin INTEGER PRIMARY KEY,
		name TEXT NOT NULL,
		password TEXT NOT NULL,
		email TEXT DEFAULT '' UNIQUE,
		phone TEXT DEFAULT ''
	)`)
	if err != nil {
		log.Fatal("Ошибка создания таблицы users:", err)
	}

	_, err = db.Exec(`CREATE TABLE IF NOT EXISTS contacts (
		user_uin INTEGER NOT NULL,
		contact_uin INTEGER NOT NULL,
		PRIMARY KEY (user_uin, contact_uin)
	)`)
	if err != nil {
		log.Fatal("Ошибка создания таблицы contacts:", err)
	}

	_, err = db.Exec(`CREATE TABLE IF NOT EXISTS messages (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		from_uin INTEGER NOT NULL,
		to_uin INTEGER NOT NULL,
		text TEXT NOT NULL,
		timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
		group_id INTEGER
	)`)
	if err != nil {
		log.Fatal("Ошибка создания таблицы messages:", err)
	}

	columns, err := db.Query("PRAGMA table_info(messages)")
	if err != nil {
		log.Fatal("Ошибка проверки схемы messages:", err)
	}
	hasGroupID := false
	for columns.Next() {
		var columnID, notNull, primaryKey int
		var columnName, columnType string
		var defaultValue interface{}
		if err := columns.Scan(&columnID, &columnName, &columnType, &notNull, &defaultValue, &primaryKey); err != nil {
			columns.Close()
			log.Fatal("Ошибка чтения схемы messages:", err)
		}
		if columnName == "group_id" {
			hasGroupID = true
		}
	}
	if err := columns.Err(); err != nil {
		columns.Close()
		log.Fatal("Ошибка чтения схемы messages:", err)
	}
	columns.Close()
	if !hasGroupID {
		if _, err := db.Exec("ALTER TABLE messages ADD COLUMN group_id INTEGER"); err != nil {
			log.Fatal("Ошибка миграции group_id в messages:", err)
		}
	}

	_, err = db.Exec(`CREATE TABLE IF NOT EXISTS groups (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		name TEXT,
		owner_uin INTEGER
	)`)
	if err != nil {
		log.Fatal("Ошибка создания таблицы groups:", err)
	}

	_, err = db.Exec(`CREATE TABLE IF NOT EXISTS group_members (
		group_id INTEGER,
		uin INTEGER,
		PRIMARY KEY (group_id, uin)
	)`)
	if err != nil {
		log.Fatal("Ошибка создания таблицы group_members:", err)
	}

	// ДОБАВЛЯЕМ ПОЛЕ AVATAR ДЛЯ СТАРОЙ БД
	db.Exec("ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT '😀'")

	log.Println("✅ База данных инициализирована")
}

// Генерация случайного 7-значного числа (от 1000000 до 9999999)
func generateRandomUIN() int {
	rand.Seed(time.Now().UnixNano())
	return rand.Intn(9000000) + 1000000 // От 1000000 до 9999999
}
func registerUser(name, password, email, phone, avatar string) (int, error) {
	phone = normalizePhone(phone)

	// 1. Генерируем случайный 7-значный UIN
	uin := generateRandomUIN()

	// 2. Преобразуем пустые строки в nil, чтобы UNIQUE работал корректно
	var emailArg interface{} = email
	if email == "" {
		emailArg = nil
	}

	var phoneArg interface{} = phone
	if phone == "" {
		phoneArg = nil
	}

	// Check the normalized value so equivalent phone formats cannot register twice.
	if phone != "" {
		var count int
		errCheck := db.QueryRow("SELECT COUNT(*) FROM users WHERE phone = ?", phone).Scan(&count)
		if errCheck != nil {
			return 0, fmt.Errorf("ошибка при проверке телефона: %w", errCheck)
		}
		if count > 0 {
			return 0, errors.New("этот номер телефона уже зарегистрирован")
		}
	}

	_, err := db.Exec(`INSERT INTO users (uin, name, password, email, phone, avatar) VALUES (?, ?, ?, ?, ?, ?)`,
		uin, name, password, emailArg, phoneArg, avatar)

	if err != nil {
		return 0, err
	}

	// Возвращаем именно наш сгенерированный UIN, а не LastInsertId
	return uin, nil
}

func getUser(uin int) (User, error) {
	var user User
	err := db.QueryRow("SELECT uin, name, password, avatar FROM users WHERE uin = ?", uin).
		Scan(&user.UIN, &user.Name, &user.Password, &user.Avatar)
	return user, err
}

func getUserByEmail(email string) (User, error) {
	var user User
	err := db.QueryRow("SELECT uin, name, password, avatar FROM users WHERE email = ?", email).
		Scan(&user.UIN, &user.Name, &user.Password, &user.Avatar)
	return user, err
}

func getUserByPhone(phone string) (User, error) {
	var user User
	err := db.QueryRow("SELECT uin, name, password, avatar FROM users WHERE phone = ?", phone).
		Scan(&user.UIN, &user.Name, &user.Password, &user.Avatar)
	return user, err
}

func addContact(userUIN, contactUIN int) error {
	_, err := db.Exec("INSERT OR IGNORE INTO contacts (user_uin, contact_uin) VALUES (?, ?)", userUIN, contactUIN)
	return err
}

func getContacts(uin int) ([]Contact, error) {
	rows, err := db.Query(`
		SELECT u.uin, u.name, u.avatar
		FROM contacts c
		JOIN users u ON c.contact_uin = u.uin
		WHERE c.user_uin = ?
	`, uin)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	contacts := make([]Contact, 0)
	for rows.Next() {
		var c Contact
		if err := rows.Scan(&c.UIN, &c.Name, &c.Avatar); err != nil {
			return nil, err
		}
		mu.RLock()
		_, online := clients[c.UIN]
		mu.RUnlock()
		if online {
			c.Status = "online"
		} else {
			c.Status = "offline"
		}
		c.Group = "General"
		contacts = append(contacts, c)
	}
	return contacts, nil
}

func saveMessage(from, to int, text string) error {
	_, err := db.Exec("INSERT INTO messages (from_uin, to_uin, text) VALUES (?, ?, ?)", from, to, text)
	return err
}

func saveGroupMessage(from, groupID int, text string) error {
	_, err := db.Exec("INSERT INTO messages (from_uin, to_uin, text, group_id) VALUES (?, ?, ?, ?)", from, groupID, text, groupID)
	return err
}

func storeUploadedFile(data []byte, extension string) (string, error) {
	if err := os.MkdirAll("uploads", 0755); err != nil {
		return "", err
	}

	randomSuffix := make([]byte, 16)
	if _, err := cryptorand.Read(randomSuffix); err != nil {
		return "", err
	}
	filename := fmt.Sprintf("%d_%s%s", time.Now().UnixNano(), hex.EncodeToString(randomSuffix), extension)
	filePath := filepath.Join("uploads", filename)
	file, err := os.OpenFile(filePath, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0644)
	if err != nil {
		return "", err
	}
	if _, err := file.Write(data); err != nil {
		file.Close()
		os.Remove(filePath)
		return "", err
	}
	if err := file.Close(); err != nil {
		os.Remove(filePath)
		return "", err
	}
	return "/uploads/" + filename, nil
}

func getMessages(uin1, uin2 int) ([]Message, error) {
	rows, err := db.Query(`
		SELECT from_uin, to_uin, text, timestamp, group_id FROM messages 
		WHERE (from_uin = ? AND to_uin = ?) OR (from_uin = ? AND to_uin = ?)
		ORDER BY timestamp ASC
	`, uin1, uin2, uin2, uin1)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var messages []Message
	for rows.Next() {
		var m Message
		if err := rows.Scan(&m.From, &m.To, &m.Text, &m.Timestamp, &m.GroupID); err != nil {
			return nil, err
		}
		messages = append(messages, m)
	}
	return messages, nil
}

func getRecentMessages(uin int) ([]Message, error) {
	rows, err := db.Query(`
		SELECT from_uin, to_uin, text, timestamp, group_id FROM (
			SELECT id, from_uin, to_uin, text, timestamp, group_id
			FROM messages
			WHERE from_uin = ? OR to_uin = ?
			ORDER BY timestamp DESC, id DESC
			LIMIT 50
		)
		ORDER BY timestamp ASC, id ASC
	`, uin, uin)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	messages := make([]Message, 0, 50)
	for rows.Next() {
		var message Message
		if err := rows.Scan(&message.From, &message.To, &message.Text, &message.Timestamp, &message.GroupID); err != nil {
			return nil, err
		}
		messages = append(messages, message)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return messages, nil
}

func broadcastStatus(uin int, status string) {
	var targets []*Client
	mu.RLock()
	for clientUIN, client := range clients {
		if clientUIN == uin {
			continue
		}
		targets = append(targets, client)
	}
	mu.RUnlock()

	for _, client := range targets {
		contacts, err := getContacts(client.uin)
		if err != nil {
			continue
		}
		for _, contact := range contacts {
			if contact.UIN == uin {
				msg := map[string]interface{}{
					"type":   "status",
					"uin":    uin,
					"status": status,
				}
				client.conn.WriteJSON(msg)
				break
			}
		}
	}
}

func handleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("Ошибка upgrade:", err)
		return
	}

	client := &Client{conn: conn}
	var currentUIN int

	defer func() {
		conn.Close()
		mu.Lock()
		if currentUIN != 0 {
			delete(clients, currentUIN)
			log.Printf("👋 Пользователь %d отключился", currentUIN)
		}
		mu.Unlock()
		if currentUIN != 0 {
			broadcastStatus(currentUIN, "offline")
		}
	}()

	for {
		_, message, err := conn.ReadMessage()
		if err != nil {
			log.Println("❌ Ошибка чтения:", err)
			break
		}

		var msg map[string]interface{}
		if err := json.Unmarshal(message, &msg); err != nil {
			log.Println("Ошибка парсинга JSON:", err)
			continue
		}

		msgType, _ := msg["type"].(string)
		log.Printf("📩 Получено: %s", msgType)

		switch msgType {
		case "register":
			handleRegister(client, msg)
		case "login":
			if uin := handleLogin(client, msg); uin != 0 {
				currentUIN = uin
			}
		case "message":
			handleMessage(msg)
		case "send_file":
			handleSendFile(client, msg)
		case "create_group":
			handleCreateGroup(client, msg)
		case "send_to_group":
			handleSendToGroup(client, msg)
		case "history":
			handleHistory(client, msg)
		case "add_contact":
			handleAddContact(client, msg)
		}
	}
}

// normalizePhone приводит номер к каноничному формату +7XXXXXXXXXX
func normalizePhone(phone string) string {
	digits := strings.Map(func(r rune) rune {
		if unicode.IsDigit(r) {
			return r
		}
		return -1
	}, phone)

	switch {
	case len(digits) == 10:
		return "+7" + digits
	case len(digits) == 11 && strings.HasPrefix(digits, "8"):
		return "+7" + digits[1:]
	case len(digits) == 11 && strings.HasPrefix(digits, "7"):
		return "+" + digits
	default:
		return ""
	}
}

func handleRegister(client *Client, msg map[string]interface{}) {
	name, _ := msg["name"].(string)
	password, _ := msg["password"].(string)
	email, _ := msg["email"].(string)
	phone, _ := msg["phone"].(string)
	rawPhone := phone // Сохраняем оригинальный ввод для проверки
	phone = normalizePhone(phone)

	// Читаем аватарку, если не указана — ставим смайлик по умолчанию
	avatar := "😀"
	if a, ok := msg["avatar"].(string); ok && a != "" {
		avatar = a
	}

	log.Printf(" Регистрация: name=%s, email=%s, phone=%s, avatar=%s", name, email, phone, avatar)

	if name == "" || password == "" {
		log.Printf("❌ Ошибка: имя или пароль пустые")
		client.conn.WriteJSON(map[string]interface{}{"type": "register", "error": "Имя и пароль обязательны"})
		return
	}

	// === НОВАЯ ВАЛИДАЦИЯ EMAIL ===
	// Проверяем регуляркой. Если пусто ("") пропускаем (для входа только по UIN/Phone), 
	// но если есть символы и они не проходят regex -> ошибка.
	if email != "" && !emailRegex.MatchString(email) {
		log.Printf("❌ Ошибка: неверный формат email: %s", email)
		client.conn.WriteJSON(map[string]interface{}{"type": "register", "error": "Неверный формат email"})
		return
	}

	// === НОВАЯ ВАЛИДАЦИЯ ТЕЛЕФОНА ===
	// Если пользователь что-то написал в поле телефона, но нормализация вернула пустую строку -> мусор.
	if rawPhone != "" && phone == "" {
		log.Printf("❌ Ошибка: неверный формат телефона: %s", rawPhone)
		client.conn.WriteJSON(map[string]interface{}{"type": "register", "error": "Неверный формат телефона"})
		return
	}

	// Приводим email к нижнему регистру перед сохранением
	uin, err := registerUser(name, password, strings.ToLower(email), phone, avatar)
	if err != nil {
		log.Printf("❌ Ошибка регистрации в БД: %v", err)
		client.conn.WriteJSON(map[string]interface{}{"type": "register", "error": "Ошибка регистрации"})
		return
	}

	log.Printf("✅ Зарегистрирован: %s (UIN: %d, Avatar: %s)", name, uin, avatar)
	client.conn.WriteJSON(map[string]interface{}{"type": "register", "uin": uin, "name": name, "avatar": avatar})
}
func handleLogin(client *Client, msg map[string]interface{}) int {
	password, _ := msg["password"].(string)
	log.Printf("🔑 Попытка входа")


	var user User
	var err error

	if uinFloat, ok := msg["uin"].(float64); ok {
		uin := int(uinFloat)
		log.Printf("Вход по UIN: %d", uin)
		user, err = getUser(uin)
	} else if email, ok := msg["email"].(string); ok && email != "" {
		// === ИСПРАВЛЕНИЕ ДЛЯ ВХОДА ПО EMAIL ===
		email = strings.ToLower(email) // Приводим к нижнему регистру
		log.Printf("Вход по E-mail: %s", email)
		user, err = getUserByEmail(email)
	} else if phone, ok := msg["phone"].(string); ok && phone != "" {
		// === ИСПРАВЛЕНИЕ ДЛЯ ВХОДА ПО ТЕЛЕФОНУ ===
		phone = normalizePhone(phone) // Нормализуем номер
		log.Printf("Вход по телефону: %s", phone)
		
		// Если после нормализации стало пусто, значит был введен мусор
		if phone == "" {
			client.conn.WriteJSON(map[string]interface{}{"type": "login", "error": "Неверный формат телефона"})
			return 0
		}
		
		user, err = getUserByPhone(phone)
	} else {
		client.conn.WriteJSON(map[string]interface{}{"type": "login", "error": "Неверные данные для входа"})
		return 0
	}
	

	log.Printf("✅ Вошел: %s (UIN: %d)", user.Name, user.UIN)

	mu.Lock()
	if oldClient, exists := clients[user.UIN]; exists {
		oldClient.conn.Close()
	}
	client.uin = user.UIN
	client.name = user.Name
	clients[user.UIN] = client
	mu.Unlock()

	client.conn.WriteJSON(map[string]interface{}{"type": "login", "uin": user.UIN, "name": user.Name, "avatar": user.Avatar})

	history, err := getRecentMessages(user.UIN)
	if err != nil {
		log.Println("Ошибка получения истории при входе:", err)
	} else {
		historyJSON, _ := json.Marshal(history)
		client.conn.WriteJSON(map[string]interface{}{"type": "history", "text": string(historyJSON)})
	}

	broadcastStatus(user.UIN, "online")

	contacts, err := getContacts(user.UIN)
	if err == nil {
		contactsJSON, _ := json.Marshal(contacts)
		client.conn.WriteJSON(map[string]interface{}{"type": "contact_list", "text": string(contactsJSON)})
	}

	return user.UIN
}

func handleAddContact(client *Client, msg map[string]interface{}) {
	contactUINFloat, _ := msg["contact_uin"].(float64)
	contactUIN := int(contactUINFloat)

	log.Printf("➕ Пользователь %d добавляет контакт %d", client.uin, contactUIN)

	if err := addContact(client.uin, contactUIN); err != nil {
		log.Println("❌ Ошибка добавления контакта:", err)
		return
	}

	contacts, err := getContacts(client.uin)
	if err == nil {
		contactsJSON, _ := json.Marshal(contacts)
		client.conn.WriteJSON(map[string]interface{}{"type": "contact_list", "text": string(contactsJSON)})
	}

	mu.RLock()
	if _, exists := clients[contactUIN]; exists {
		mu.RUnlock()
		client.conn.WriteJSON(map[string]interface{}{
			"type":   "status",
			"uin":    contactUIN,
			"status": "online",
		})
	} else {
		mu.RUnlock()
	}
}

func handleCreateGroup(client *Client, msg map[string]interface{}) {
	name, _ := msg["name"].(string)
	memberValues, ok := msg["member_uins"].([]interface{})
	if client.uin == 0 || strings.TrimSpace(name) == "" || !ok {
		client.conn.WriteJSON(map[string]interface{}{"type": "group_error", "error": "Требуются авторизация, имя группы и список участников"})
		return
	}

	members := []int{client.uin}
	seen := map[int]bool{client.uin: true}
	for _, value := range memberValues {
		memberFloat, ok := value.(float64)
		if !ok {
			continue
		}
		memberUIN := int(memberFloat)
		if memberUIN > 0 && !seen[memberUIN] {
			members = append(members, memberUIN)
			seen[memberUIN] = true
		}
	}

	tx, err := db.Begin()
	if err != nil {
		client.conn.WriteJSON(map[string]interface{}{"type": "group_error", "error": "Не удалось создать группу"})
		return
	}
	defer tx.Rollback()

	result, err := tx.Exec("INSERT INTO groups (name, owner_uin) VALUES (?, ?)", name, client.uin)
	if err != nil {
		client.conn.WriteJSON(map[string]interface{}{"type": "group_error", "error": "Не удалось создать группу"})
		return
	}
	groupID, err := result.LastInsertId()
	if err != nil {
		client.conn.WriteJSON(map[string]interface{}{"type": "group_error", "error": "Не удалось создать группу"})
		return
	}

	for _, memberUIN := range members {
		if _, err := tx.Exec("INSERT INTO group_members (group_id, uin) VALUES (?, ?)", groupID, memberUIN); err != nil {
			client.conn.WriteJSON(map[string]interface{}{"type": "group_error", "error": "Не удалось добавить участников группы"})
			return
		}
	}
	if err := tx.Commit(); err != nil {
		client.conn.WriteJSON(map[string]interface{}{"type": "group_error", "error": "Не удалось создать группу"})
		return
	}

	client.conn.WriteJSON(map[string]interface{}{"type": "group_created", "id": groupID, "members": members})
}

func handleSendToGroup(client *Client, msg map[string]interface{}) {
	groupIDFloat, ok := msg["group_id"].(float64)
	text, textOK := msg["text"].(string)
	if client.uin == 0 || !ok || !textOK {
		client.conn.WriteJSON(map[string]interface{}{"type": "group_error", "error": "Требуются авторизация, ID группы и текст сообщения"})
		return
	}
	groupID := int(groupIDFloat)

	rows, err := db.Query("SELECT uin FROM group_members WHERE group_id = ?", groupID)
	if err != nil {
		client.conn.WriteJSON(map[string]interface{}{"type": "group_error", "error": "Не удалось получить участников группы"})
		return
	}
	var members []int
	senderIsMember := false
	for rows.Next() {
		var memberUIN int
		if err := rows.Scan(&memberUIN); err != nil {
			rows.Close()
			client.conn.WriteJSON(map[string]interface{}{"type": "group_error", "error": "Не удалось получить участников группы"})
			return
		}
		members = append(members, memberUIN)
		if memberUIN == client.uin {
			senderIsMember = true
		}
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		client.conn.WriteJSON(map[string]interface{}{"type": "group_error", "error": "Не удалось получить участников группы"})
		return
	}
	rows.Close()
	if !senderIsMember {
		client.conn.WriteJSON(map[string]interface{}{"type": "group_error", "error": "Вы не состоите в этой группе"})
		return
	}

	if err := saveGroupMessage(client.uin, groupID, text); err != nil {
		log.Println("Ошибка сохранения группового сообщения:", err)
		client.conn.WriteJSON(map[string]interface{}{"type": "group_error", "error": "Не удалось сохранить сообщение"})
		return
	}

	var recipients []*Client
	mu.RLock()
	for _, memberUIN := range members {
		if recipient, exists := clients[memberUIN]; exists {
			recipients = append(recipients, recipient)
		}
	}
	mu.RUnlock()

	outgoing := map[string]interface{}{
		"type":     "message",
		"from":     client.uin,
		"to":       groupID,
		"text":     text,
		"group_id": groupID,
		"is_group": true,
	}
	for _, recipient := range recipients {
		if err := recipient.conn.WriteJSON(outgoing); err != nil {
			log.Printf("Ошибка доставки группового сообщения пользователю %d: %v", recipient.uin, err)
		}
	}
}

func handleSendFile(client *Client, msg map[string]interface{}) {
	if client.uin == 0 {
		client.conn.WriteJSON(map[string]interface{}{"type": "file_error", "error": "Требуется авторизация"})
		return
	}

	encodedData, ok := msg["data"].(string)
	if !ok || len(encodedData) > base64.StdEncoding.EncodedLen(maxUploadedFileSize) {
		client.conn.WriteJSON(map[string]interface{}{"type": "file_error", "error": "Файл превышает максимальный размер 5 МБ или данные отсутствуют"})
		return
	}
	data, err := base64.StdEncoding.DecodeString(encodedData)
	if err != nil {
		client.conn.WriteJSON(map[string]interface{}{"type": "file_error", "error": "Некорректные Base64-данные"})
		return
	}
	if len(data) > maxUploadedFileSize {
		client.conn.WriteJSON(map[string]interface{}{"type": "file_error", "error": "Файл превышает максимальный размер 5 МБ"})
		return
	}

	mimeValue, _ := msg["mime_type"].(string)
	mediaType, _, err := mime.ParseMediaType(mimeValue)
	if err != nil || mediaType == "" {
		client.conn.WriteJSON(map[string]interface{}{"type": "file_error", "error": "Некорректный MIME-тип"})
		return
	}
	extension := ".bin"
	if extensions, err := mime.ExtensionsByType(mediaType); err == nil && len(extensions) > 0 && !strings.ContainsAny(extensions[0], `/\\`) {
		extension = extensions[0]
	}

	groupID := 0
	isGroup := false
	toUIN := 0
	var recipients []*Client
	if groupValue, isGroupMessage := msg["group_id"]; isGroupMessage {
		groupIDFloat, valid := groupValue.(float64)
		if !valid || groupIDFloat <= 0 {
			client.conn.WriteJSON(map[string]interface{}{"type": "file_error", "error": "Некорректный ID группы"})
			return
		}
		groupID = int(groupIDFloat)
		isGroup = true

		rows, err := db.Query("SELECT uin FROM group_members WHERE group_id = ?", groupID)
		if err != nil {
			client.conn.WriteJSON(map[string]interface{}{"type": "file_error", "error": "Не удалось получить участников группы"})
			return
		}
		members := make([]int, 0)
		senderIsMember := false
		for rows.Next() {
			var memberUIN int
			if err := rows.Scan(&memberUIN); err != nil {
				rows.Close()
				client.conn.WriteJSON(map[string]interface{}{"type": "file_error", "error": "Не удалось получить участников группы"})
				return
			}
			members = append(members, memberUIN)
			if memberUIN == client.uin {
				senderIsMember = true
			}
		}
		if err := rows.Err(); err != nil {
			rows.Close()
			client.conn.WriteJSON(map[string]interface{}{"type": "file_error", "error": "Не удалось получить участников группы"})
			return
		}
		rows.Close()
		if !senderIsMember {
			client.conn.WriteJSON(map[string]interface{}{"type": "file_error", "error": "Вы не состоите в этой группе"})
			return
		}

		mu.RLock()
		for _, memberUIN := range members {
			if recipient, exists := clients[memberUIN]; exists {
				recipients = append(recipients, recipient)
			}
		}
		mu.RUnlock()
	} else {
		toFloat, valid := msg["to"].(float64)
		if !valid || toFloat <= 0 {
			client.conn.WriteJSON(map[string]interface{}{"type": "file_error", "error": "Не указан получатель"})
			return
		}
		toUIN = int(toFloat)
		mu.RLock()
		if recipient, exists := clients[toUIN]; exists {
			recipients = append(recipients, recipient)
		}
		mu.RUnlock()
	}

	fileURL, err := storeUploadedFile(data, extension)
	if err != nil {
		log.Println("Ошибка сохранения файла:", err)
		client.conn.WriteJSON(map[string]interface{}{"type": "file_error", "error": "Не удалось сохранить файл"})
		return
	}
	if isGroup {
		err = saveGroupMessage(client.uin, groupID, fileURL)
	} else {
		err = saveMessage(client.uin, toUIN, fileURL)
	}
	if err != nil {
		os.Remove(filepath.Join("uploads", filepath.Base(fileURL)))
		log.Println("Ошибка сохранения сообщения с файлом:", err)
		client.conn.WriteJSON(map[string]interface{}{"type": "file_error", "error": "Не удалось сохранить сообщение"})
		return
	}

	outgoing := map[string]interface{}{
		"type":      "message",
		"from":      client.uin,
		"to":        toUIN,
		"text":      fileURL,
		"is_file":   true,
		"mime_type": mediaType,
	}
	if isGroup {
		outgoing["to"] = groupID
		outgoing["group_id"] = groupID
		outgoing["is_group"] = true
	}
	for _, recipient := range recipients {
		if err := recipient.conn.WriteJSON(outgoing); err != nil {
			log.Printf("Ошибка доставки файла пользователю %d: %v", recipient.uin, err)
		}
	}
}

func handleMessage(msg map[string]interface{}) {
	fromFloat, _ := msg["from"].(float64)
	toFloat, _ := msg["to"].(float64)
	text, _ := msg["text"].(string)

	from := int(fromFloat)
	to := int(toFloat)

	log.Printf("📨 Сообщение от %d к %d: %s", from, to, text)

	if err := saveMessage(from, to, text); err != nil {
		log.Println("❌ Ошибка сохранения:", err)
		return
	}

	mu.RLock()
	recipient, exists := clients[to]
	mu.RUnlock()

	if exists {
		recipient.conn.WriteJSON(msg)
		log.Printf("✅ Доставлено пользователю %d", to)
	} else {
		log.Printf("⚠️ Пользователь %d не в сети", to)
	}
}

func handleHistory(client *Client, msg map[string]interface{}) {
	uinFloat, _ := msg["uin"].(float64)
	uin := int(uinFloat)

	messages, err := getMessages(client.uin, uin)
	if err != nil {
		log.Println("Ошибка получения истории:", err)
		return
	}

	messagesJSON, _ := json.Marshal(messages)
	client.conn.WriteJSON(map[string]interface{}{"type": "history", "text": string(messagesJSON)})
	log.Printf("📜 История: %d сообщений для UIN %d", len(messages), client.uin)
}

func main() {
	initDB()
	if err := os.MkdirAll("uploads", 0755); err != nil {
		log.Fatal("Ошибка создания папки uploads:", err)
	}
	http.HandleFunc("/ws", handleWebSocket)
	http.Handle("/uploads/", http.StripPrefix("/uploads/", http.FileServer(http.Dir("uploads"))))
	log.Println("🚀 Сервер ICQ запущен на http://localhost:8080")
	log.Println("🔌 WebSocket: ws://localhost:8080/ws")

	if err := http.ListenAndServe("0.0.0.0:8080", nil); err != nil {
		log.Fatal("Ошибка запуска:", err)
	}
}
