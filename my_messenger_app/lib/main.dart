import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await _initNotifications();
  runApp(const ICQMessenger());
}

final FlutterLocalNotificationsPlugin flutterLocalNotificationsPlugin = FlutterLocalNotificationsPlugin();

// Глобальный ключ навигатора для перехода из уведомлений
final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

// Глобальные переменные для хранения текущего подключения
WebSocketChannel? _currentChannel;
Stream<dynamic>? _currentBroadcastStream;

Future<void> _initNotifications() async {
  const AndroidInitializationSettings initializationSettingsAndroid = AndroidInitializationSettings('@mipmap/ic_launcher');
  const DarwinInitializationSettings initializationSettingsDarwin = DarwinInitializationSettings(
    requestAlertPermission: true, requestBadgePermission: true, requestSoundPermission: true,
  );
  const WindowsInitializationSettings windowsInitializationSettings = WindowsInitializationSettings(
    appName: 'ICQ Messenger', appUserModelId: 'ICQ.Messenger.App', guid: 'b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e',
  );

  const InitializationSettings initializationSettings = InitializationSettings(
    android: initializationSettingsAndroid, iOS: initializationSettingsDarwin, macOS: initializationSettingsDarwin, windows: windowsInitializationSettings,
  );

  await flutterLocalNotificationsPlugin.initialize(
    initializationSettings,
    onDidReceiveNotificationResponse: (NotificationResponse response) {
      _handleNotificationTap(response.payload);
    },
  );
  print('✅ Уведомления инициализированы (включая Windows)');
}

// Обработчик клика по уведомлению
void _handleNotificationTap(String? payload) {
  if (payload == null || payload.isEmpty) return;
  
  try {
    final data = jsonDecode(payload) as Map<String, dynamic>;
    final contactUIN = data['contactUIN'] as int;
    final contactName = data['contactName'] as String;
    final myUIN = data['myUIN'] as int;
    
    print(' Клик по уведомлению: $contactName (UIN: $contactUIN)');
    
    // Используем существующее подключение, если оно есть
    final channel = _currentChannel;
    final broadcastStream = _currentBroadcastStream;
    
    if (channel != null && broadcastStream != null) {
      // Приложение открыто — открываем чат в существующем навигаторе
      navigatorKey.currentState?.push(MaterialPageRoute(
        builder: (_) => ChatScreen(
          myUIN: myUIN,
          contactUIN: contactUIN,
          contactName: contactName,
          broadcastStream: broadcastStream,
          channel: channel,
        ),
      ));
    } else {
      print('⚠️ Подключение отсутствует, приложение было закрыто');
    }
  } catch (e) {
    print('❌ Ошибка обработки клика: $e');
  }
}

final AudioPlayer _messagePlayer = AudioPlayer();
final AudioPlayer _onlinePlayer = AudioPlayer();
final AudioPlayer _loginPlayer = AudioPlayer();

class ICQMessenger extends StatelessWidget {
  const ICQMessenger({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ICQ Messenger',
      navigatorKey: navigatorKey,
      theme: ThemeData(primarySwatch: Colors.green, scaffoldBackgroundColor: const Color(0xFFF5F5F5), fontFamily: 'Segoe UI'),
      home: const LoginScreen(),
    );
  }
}

// ============================================================
// ЭКРАН ВХОДА
// ============================================================
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _uinController = TextEditingController();
  final _phoneController = TextEditingController();
  final _nameController = TextEditingController();
  final _passwordController = TextEditingController();
  
  String _selectedAvatar = '😀';
  final List<String> _avatars = [
    '😀', '😎', '🤠', '👻', '🤖', 
    '👽', '🐱', '🐶', '🦊', '🐸'
  ];

  bool _isLogin = true;
  bool _rememberMe = false;
  bool _usePhone = false;
  String _message = '';
  WebSocketChannel? _channel;
  Stream<dynamic>? _broadcastStream;
  int? _myUIN;
  String? _myName;

  @override
  void initState() { super.initState(); _checkSavedSession(); }
  @override
  void dispose() {
    _uinController.dispose(); _phoneController.dispose(); _nameController.dispose(); _passwordController.dispose();
    super.dispose();
  }

  Future<void> _connect() async {
    try {
      _channel = WebSocketChannel.connect(Uri.parse('ws://127.0.0.1:8080/ws'));
      _broadcastStream = _channel!.stream.asBroadcastStream();
      _broadcastStream!.listen((data) {
        final msg = jsonDecode(data);
        if (!mounted) return;
        setState(() {
          if (msg['type'] == 'register') {
            if (msg['error'] != null) { 
              _message = msg['error']; 
            } else { 
              _myUIN = msg['uin']; 
              _myName = msg['name'];
              _selectedAvatar = msg['avatar'] ?? '😀'; // <-- СОХРАНЯЕМ АВАТАРКУ
              _message = '✅ Регистрация успешна!\nВаш UIN: $_myUIN'; 
            }
          } else if (msg['type'] == 'login') {
            if (msg['error'] != null) { 
              _message = msg['error']; 
            } else {
              _myUIN = msg['uin']; 
              _myName = msg['name'];
              _selectedAvatar = msg['avatar'] ?? '😀'; // <-- СОХРАНЯЕМ АВАТАРКУ
              try { _loginPlayer.play(AssetSource('sounds/02_login.mp3')); } catch(e) {}
              if (_rememberMe) _saveSession();
              Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => ContactListScreen(
                uin: _myUIN!, 
                name: _myName!, 
                avatar: _selectedAvatar, // <-- ПЕРЕДАЁМ АВАТАРКУ
                broadcastStream: _broadcastStream!, 
                channel: _channel!,
              )));
            }
          }
        });
      });
    } catch (e) {
      if (mounted) setState(() { _message = 'Не удалось подключиться к серверу'; });
    }
  }

    Future<void> _sendRequest() async {
    if (_channel == null) await _connect();
    Map<String, dynamic> request;
    
    if (_usePhone) {
      request = {
        'type': _isLogin ? 'login' : 'register',
        'phone': _phoneController.text,
        'password': _passwordController.text,
        'name': _nameController.text,
        'avatar': _selectedAvatar, // <-- ДОБАВЛЕНО
      };
    } else {
      String uinOrEmail = _uinController.text;
      bool isEmail = uinOrEmail.contains('@');
      if (isEmail) {
        request = {
          'type': _isLogin ? 'login' : 'register',
          'email': uinOrEmail,
          'password': _passwordController.text,
          'name': _nameController.text,
          'avatar': _selectedAvatar, // <-- ДОБАВЛЕНО
        };
      } else {
        request = {
          'type': _isLogin ? 'login' : 'register',
          'uin': int.tryParse(uinOrEmail) ?? 0,
          'password': _passwordController.text,
          'name': _nameController.text,
          'avatar': _selectedAvatar, // <-- ДОБАВЛЕНО
        };
      }
    }
    print('📤 Отправляю на сервер: $request');
    _channel!.sink.add(jsonEncode(request));
  }

  Future<void> _saveSession() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('icq_remember', true);
    await prefs.setString('icq_password', _passwordController.text);
    if (_usePhone) {
      await prefs.setString('icq_login_type', 'phone');
      await prefs.setString('icq_phone', _phoneController.text);
      await prefs.setString('icq_name', _nameController.text);
    } else {
      String uinOrEmail = _uinController.text;
      bool isEmail = uinOrEmail.contains('@');
      if (isEmail) {
        await prefs.setString('icq_login_type', 'email');
        await prefs.setString('icq_email', uinOrEmail);
        await prefs.setString('icq_name', _nameController.text);
      } else {
        await prefs.setString('icq_login_type', 'uin');
        await prefs.setInt('icq_uin', int.tryParse(uinOrEmail) ?? 0);
      }
    }
    print('💾 Сессия сохранена');
  }

  Future<void> _checkSavedSession() async {
    final prefs = await SharedPreferences.getInstance();
    final remember = prefs.getBool('icq_remember') ?? false;
    if (!remember) return;
    
    final loginType = prefs.getString('icq_login_type') ?? 'uin';
    final password = prefs.getString('icq_password') ?? '';
    
    // Если пароль пустой — сессия невалидна, не пытаемся войти
    if (password.isEmpty) {
      print('⚠️ Пароль пустой, авто-вход отменён');
      await prefs.remove('icq_remember');
      return;
    }
    
    print('🔍 Загружаю сохраненную сессию: тип=$loginType');
    
    setState(() {
      _passwordController.text = password;
      _rememberMe = true;
      _isLogin = true;
      
      if (loginType == 'phone') {
        _usePhone = true;
        _phoneController.text = prefs.getString('icq_phone') ?? '';
        _nameController.text = prefs.getString('icq_name') ?? '';
      } else if (loginType == 'email') {
        _usePhone = false;
        _uinController.text = prefs.getString('icq_email') ?? '';
        _nameController.text = prefs.getString('icq_name') ?? '';
      } else {
        _usePhone = false;
        final uin = prefs.getInt('icq_uin') ?? 0;
        // Если UIN = 0, значит данные некорректны — не пытаемся войти
        if (uin == 0) {
          print('⚠️ UIN = 0, авто-вход отменён');
          _passwordController.clear();
          _rememberMe = false;
          return;
        }
        _uinController.text = uin.toString();
      }
    });
    
    await Future.delayed(const Duration(milliseconds: 1000));
    await _connect();
    _sendRequest();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: Center(
        child: Container(
          width: 400, padding: const EdgeInsets.all(40),
          decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(10), boxShadow: [BoxShadow(color: Colors.black12, blurRadius: 20, spreadRadius: 5)]),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Container(width: 120, height: 120, decoration: BoxDecoration(color: Colors.green[100], shape: BoxShape.circle, border: Border.all(color: Colors.green, width: 3)), child: const Icon(Icons.local_florist, size: 80, color: Colors.green)),
            const SizedBox(height: 30),
            Container(
              decoration: BoxDecoration(border: Border.all(color: Colors.grey[300]!), borderRadius: BorderRadius.circular(25)),
              child: Row(children: [
                Expanded(child: TextButton(onPressed: () => setState(() => _usePhone = false), style: TextButton.styleFrom(backgroundColor: !_usePhone ? Colors.green : Colors.transparent, foregroundColor: !_usePhone ? Colors.white : Colors.black54, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(25))), child: const Text('UIN / E-mail'))),
                Expanded(child: TextButton(onPressed: () => setState(() => _usePhone = true), style: TextButton.styleFrom(backgroundColor: _usePhone ? Colors.green : Colors.transparent, foregroundColor: _usePhone ? Colors.white : Colors.black54, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(25))), child: const Text('Телефон'))),
              ]),
            ),
          if (!_isLogin)
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Выберите аватарку:',
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Colors.black54),
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: _avatars.map((avatar) {
                    final isSelected = _selectedAvatar == avatar;
                    return GestureDetector(
                      onTap: () {
                        setState(() {
                          _selectedAvatar = avatar;
                        });
                      },
                      child: Container(
                        width: 45,
                        height: 45,
                        decoration: BoxDecoration(
                          color: isSelected ? Colors.green.withOpacity(0.2) : Colors.grey[200],
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(
                            color: isSelected ? Colors.green : Colors.transparent,
                            width: 2,
                          ),
                        ),
                        child: Center(
                          child: Text(
                            avatar,
                            style: const TextStyle(fontSize: 24),
                          ),
                        ),
                      ),
                    );
                  }).toList(),
                ),
                const SizedBox(height: 15),
              ],
            ),
            const SizedBox(height: 15),
            if (_usePhone) ...[
              if (!_isLogin) ...[
                TextField(controller: _phoneController, decoration: const InputDecoration(labelText: 'Телефон', border: OutlineInputBorder(), prefixIcon: Icon(Icons.phone, color: Colors.green)), keyboardType: TextInputType.phone),
                const SizedBox(height: 15),
                TextField(controller: _nameController, decoration: const InputDecoration(labelText: 'Ваше имя', border: OutlineInputBorder(), prefixIcon: Icon(Icons.person, color: Colors.green))),
                const SizedBox(height: 15),
              ] else ...[
                TextField(controller: _phoneController, decoration: const InputDecoration(labelText: 'Телефон', border: OutlineInputBorder(), prefixIcon: Icon(Icons.phone, color: Colors.green)), keyboardType: TextInputType.phone),
                const SizedBox(height: 15),
              ],
            ] else ...[
              if (!_isLogin) ...[
                TextField(controller: _uinController, decoration: const InputDecoration(labelText: 'E-mail или оставьте пустым для авто-UIN', border: OutlineInputBorder(), prefixIcon: Icon(Icons.email, color: Colors.green)), keyboardType: TextInputType.emailAddress),
                const SizedBox(height: 15),
                TextField(controller: _nameController, decoration: const InputDecoration(labelText: 'Ваше имя', border: OutlineInputBorder(), prefixIcon: Icon(Icons.person, color: Colors.green))),
                const SizedBox(height: 15),
              ] else ...[
                TextField(controller: _uinController, decoration: const InputDecoration(labelText: 'UIN или E-mail', border: OutlineInputBorder(), prefixIcon: Icon(Icons.person, color: Colors.green))),
                const SizedBox(height: 15),
              ],
            ],
            TextField(controller: _passwordController, decoration: const InputDecoration(labelText: 'Пароль', border: OutlineInputBorder(), prefixIcon: Icon(Icons.lock, color: Colors.green)), obscureText: true),
            if (_isLogin) ...[
              const SizedBox(height: 10),
              Row(children: [Checkbox(value: _rememberMe, onChanged: (val) => setState(() => _rememberMe = val!)), const Text('Запомнить'), const Spacer(), TextButton(onPressed: () {}, child: const Text('Забыли пароль?'))]),
            ],
            const SizedBox(height: 20),
            SizedBox(width: double.infinity, height: 45, child: ElevatedButton.icon(onPressed: _sendRequest, icon: Icon(_isLogin ? Icons.login : Icons.person_add), label: Text(_isLogin ? 'Войти' : 'Зарегистрироваться'), style: ElevatedButton.styleFrom(backgroundColor: Colors.green, foregroundColor: Colors.white, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(25))))),
            const SizedBox(height: 15),
            TextButton(onPressed: () { setState(() { _isLogin = !_isLogin; _message = ''; _passwordController.clear(); }); }, child: Text(_isLogin ? 'Нет аккаунта? Зарегистрироваться' : 'Уже есть аккаунт? Войти')),
            if (_message.isNotEmpty) ...[const SizedBox(height: 15), Text(_message, style: TextStyle(color: _message.contains('✅') ? Colors.green : Colors.red, fontSize: 14), textAlign: TextAlign.center)],
            const SizedBox(height: 20), const Divider(), const SizedBox(height: 10),
            Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              IconButton(icon: const Icon(Icons.facebook, color: Colors.blue), onPressed: () {}),
              IconButton(icon: const Icon(Icons.alternate_email, color: Colors.orange), onPressed: () {}),
              IconButton(icon: const Icon(Icons.videocam, color: Colors.green), onPressed: () {}),
            ]),
          ]),
        ),
      ),
    );
  }
}

// ============================================================
// СПИСОК КОНТАКТОВ (с боковой панелью и группами)
// ============================================================
class ContactListScreen extends StatefulWidget {
  final int uin; final String name; final String avatar; final Stream<dynamic> broadcastStream; final WebSocketChannel channel;
  const ContactListScreen({super.key, required this.uin, required this.name, required this.avatar, required this.broadcastStream, required this.channel});
  @override
  State<ContactListScreen> createState() => _ContactListScreenState();
}

class _ContactListScreenState extends State<ContactListScreen> {
  List<Map<String, dynamic>> _contacts = [];
  Map<String, List<Map<String, dynamic>>> _groupedContacts = {};
  bool _isInitialized = false;
  String _searchQuery = '';
  String? _myAvatar;

  @override
  void initState() {
    super.initState();
    _myAvatar = widget.avatar;
    _currentChannel = widget.channel;
    _currentBroadcastStream = widget.broadcastStream;
    _loadContacts();
    _setupStream();
  }

  void _setupStream() {
    widget.broadcastStream.listen((data) {
      final msg = jsonDecode(data);
      if (!mounted) return;
      if (msg['type'] == 'status') { _handleStatusChange(msg); } 
      else if (msg['type'] == 'contact_list') { _handleContactList(msg); } 
      else if (msg['type'] == 'message' && msg['to'] == widget.uin) { _handleIncomingMessage(msg); }
    });
  }

  void _handleStatusChange(Map<String, dynamic> msg) {
    final uin = msg['uin'] as int;
    final status = msg['status'] as String;
    final index = _contacts.indexWhere((c) => c['uin'] == uin);
    if (index != -1) {
      final oldStatus = _contacts[index]['status'];
      setState(() { _contacts[index]['status'] = status; _groupContacts(); });
      _saveContacts();
      if (oldStatus != 'online' && status == 'online' && _isInitialized) {
        try { _onlinePlayer.play(AssetSource('sounds/03_user_online.mp3')); } catch(e) {}
      }
    }
  }

  void _handleContactList(Map<String, dynamic> msg) {
    final contacts = jsonDecode(msg['text']) as List;
    setState(() { _contacts = contacts.map((c) => Map<String, dynamic>.from(c)).toList(); _groupContacts(); });
    _saveContacts();
    if (!_isInitialized) _isInitialized = true;
  }

  void _handleIncomingMessage(Map<String, dynamic> msg) {
    try { _messagePlayer.play(AssetSource('sounds/01_message.mp3')); } catch(e) {}
    _showMessageNotification(msg['from'], msg['text']);
  }

  void _groupContacts() {
    _groupedContacts = {'General': [], 'Знакомые': [], 'Общие': [], 'Работа': []};
    for (var contact in _contacts) {
      String group = contact['group'] ?? 'General';
      if (!_groupedContacts.containsKey(group)) group = 'General';
      _groupedContacts[group]!.add(contact);
    }
  }

  Future<void> _loadContacts() async {
    final prefs = await SharedPreferences.getInstance();
    final contactsJson = prefs.getString('icq_contacts_${widget.uin}');
    if (contactsJson != null && contactsJson.isNotEmpty && contactsJson != '[]') {
      final contacts = jsonDecode(contactsJson) as List;
      setState(() { _contacts = contacts.map((c) => Map<String, dynamic>.from(c)).toList(); _groupContacts(); });
    }
  }

  Future<void> _saveContacts() async {
    if (_contacts.isEmpty) return;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('icq_contacts_${widget.uin}', jsonEncode(_contacts));
  }

  void _showMessageNotification(int fromUin, String text) {
    final sender = _contacts.firstWhere((c) => c['uin'] == fromUin, orElse: () => {'name': 'Неизвестно', 'uin': fromUin});
    final senderName = sender['name'] ?? 'UIN $fromUin';
    print('🔔 Уведомление: $senderName - $text');

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Row(children: [const Icon(Icons.message, color: Colors.white), const SizedBox(width: 12), Expanded(child: Text('$senderName: $text', style: const TextStyle(fontWeight: FontWeight.bold)))]),
        backgroundColor: Colors.green[700], behavior: SnackBarBehavior.floating, duration: const Duration(seconds: 4), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ));
    }

    try {
      const androidDetails = AndroidNotificationDetails('icq_channel', 'ICQ Messages', channelDescription: 'Notifications for ICQ messages', importance: Importance.high, priority: Priority.high);
      const details = NotificationDetails(android: androidDetails, windows: const WindowsNotificationDetails());
      
      final payload = jsonEncode({
        'contactUIN': fromUin,
        'contactName': senderName,
        'myUIN': widget.uin,
      });
      
      flutterLocalNotificationsPlugin.show(
        DateTime.now().millisecondsSinceEpoch.remainder(100000),
        '📨 Новое сообщение',
        '$senderName: $text',
        details,
        payload: payload,
      );
    } catch (e) { print('❌ Ошибка уведомления: $e'); }
  }

  Future<void> _logout() async {
    widget.channel.sink.close();
    // Очищаем глобальные переменные
    _currentChannel = null;
    _currentBroadcastStream = null;
    
    final prefs = await SharedPreferences.getInstance();
    // Удаляем ВСЕ данные сессии
    await prefs.remove('icq_uin');
    await prefs.remove('icq_password');
    await prefs.remove('icq_remember');
    await prefs.remove('icq_login_type');
    await prefs.remove('icq_phone');
    await prefs.remove('icq_email');
    await prefs.remove('icq_name');
    
    if (mounted) Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => const LoginScreen()));
  }

  Color _getStatusColor(String status) {
    switch (status) { case 'online': return Colors.green; case 'away': return Colors.orange; case 'dnd': return Colors.red; default: return Colors.grey; }
  }

  IconData _getStatusIcon(String status) {
    switch (status) { case 'online': return Icons.local_florist; case 'away': return Icons.access_time; case 'dnd': return Icons.do_not_disturb; default: return Icons.circle; }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
            appBar: AppBar(
        backgroundColor: Colors.green[700],
        title: Row(children: [
          CircleAvatar(
            backgroundColor: Colors.white,
            radius: 25,
            child: Text(
              _myAvatar ?? '😀',
              style: const TextStyle(fontSize: 30),
            ),
          ),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(widget.name, style: const TextStyle(fontWeight: FontWeight.bold)),
              Text('UIN: ${widget.uin}', style: const TextStyle(fontSize: 12)),
            ],
          ),
          const Spacer(),
          IconButton(icon: const Icon(Icons.logout), onPressed: _logout),
        ]),
      ),
      body: Row(
        children: [
          Container(width: 60, color: Colors.green[900], child: Column(children: [
            IconButton(icon: const Icon(Icons.home, color: Colors.white), onPressed: () {}),
            IconButton(icon: const Icon(Icons.chat, color: Colors.white), onPressed: () {}),
            IconButton(icon: const Icon(Icons.phone, color: Colors.white), onPressed: () {}),
            IconButton(icon: const Icon(Icons.videocam, color: Colors.white), onPressed: () {}),
            const Spacer(),
            IconButton(icon: const Icon(Icons.settings, color: Colors.white), onPressed: () {}),
          ])),
          Expanded(child: Column(children: [
            Padding(padding: const EdgeInsets.all(8.0), child: TextField(
              decoration: InputDecoration(hintText: 'Поиск контактов', prefixIcon: const Icon(Icons.search), border: OutlineInputBorder(borderRadius: BorderRadius.circular(20)), filled: true, fillColor: Colors.grey[100]),
              onChanged: (val) => setState(() => _searchQuery = val),
            )),
            Expanded(child: _groupedContacts.isEmpty 
              ? const Center(child: Text('Список контактов пуст.\nДобавьте друга по UIN!'))
              : ListView.builder(itemCount: _groupedContacts.length, itemBuilder: (context, groupIndex) {
                  String groupName = _groupedContacts.keys.elementAt(groupIndex);
                  List<Map<String, dynamic>> groupContacts = _groupedContacts[groupName]!;
                  if (groupContacts.isEmpty) return const SizedBox.shrink();
                  return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Padding(padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8), child: Text('$groupName (${groupContacts.length})', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.grey[700], fontSize: 12))),
                    ...groupContacts.map((contact) {
                     return ListTile(
  leading: CircleAvatar(
    backgroundColor: _getStatusColor(contact['status'] ?? 'offline'),
    child: Text(
      contact['avatar'] ?? '😀',
      style: const TextStyle(fontSize: 20),
    ),
  ),
  title: Text(contact['name'] ?? 'Неизвестно'),
  subtitle: Text('UIN: ${contact['uin']}'),
  trailing: Icon(
    _getStatusIcon(contact['status'] ?? 'offline'),
    color: _getStatusColor(contact['status'] ?? 'offline'),
    size: 16,
  ),
  onTap: () {
    Navigator.push(context, MaterialPageRoute(
      builder: (_) => ChatScreen(
        myUIN: widget.uin,
        contactUIN: contact['uin'],
        contactName: contact['name'] ?? 'Контакт',
        contactAvatar: contact['avatar'] ?? '😀',
        broadcastStream: widget.broadcastStream,
        channel: widget.channel,
      ),
    ));
  },
);
                    }).toList(),
                  ]);
                }),
            ),
          ])),
        ],
      ),
      floatingActionButton: FloatingActionButton(onPressed: () {
        final uinController = TextEditingController();
        showDialog(context: context, builder: (context) => AlertDialog(
          title: const Text('Добавить контакт'),
          content: TextField(controller: uinController, decoration: const InputDecoration(labelText: 'UIN контакта'), keyboardType: TextInputType.number),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Отмена')),
            TextButton(onPressed: () {
              final newUin = int.tryParse(uinController.text);
              if (newUin != null) widget.channel.sink.add(jsonEncode({'type': 'add_contact', 'contact_uin': newUin}));
              Navigator.pop(context);
            }, child: const Text('Добавить')),
          ],
        ));
      }, child: const Icon(Icons.add)),
    );
  }
}

// ============================================================
// ЭКРАН ЧАТА
// ============================================================
class ChatScreen extends StatefulWidget {
  final int myUIN; final int contactUIN; final String contactName; final String contactAvatar; final Stream<dynamic> broadcastStream; final WebSocketChannel channel;
  const ChatScreen({super.key, required this.myUIN, required this.contactUIN, required this.contactName, this.contactAvatar = '😀', required this.broadcastStream, required this.channel});
  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _messageController = TextEditingController();
  List<Map<String, dynamic>> _messages = [];
  bool _showEmoji = false;
  String? _myAvatar;

  final List<String> _emojis = ['😀', '😃', '😄', '😁', '😆', '😅', '🤣', '😂', '🙂', '🙃', '😉', '😊', '😇', '🥰', '😍', '🤩', '😘', '😗', '😚', '😙', '🥲', '', '😛', '😜', '', '😝', '🤑', '🤗', '🤭', '', '🤔', '🤐', '🤨', '😐', '', '😶', '😏', '', '🙄', '😬', '🤥', '😌', '😔', '😪', '🤤', '😴', '😷', '🤒', '', '🤢', '🤮', '🤧', '🥵', '🥶', '🥴', '😵', '🤯', '🤠', '🥳', '🥸', '😎', '🤓', '🧐', '😕', '😟', '🙁', '☹️', '😮', '😯', '😲', '😳', '', '😦', '😧', '', '😰', '😥', '', '😭', '😱', '', '😣', '😞', '', '😩', '😫', '', '😤', '😡', '😠', '🤬', '👿', '💀', '☠️', '', '🤡', '👹', '👺', '👻', ''];

  @override
  void initState() { super.initState(); _myAvatar = '😀';_loadHistory(); _setupStream(); }
  void _loadHistory() { widget.channel.sink.add(jsonEncode({'type': 'history', 'uin': widget.contactUIN})); }
  void _setupStream() {
    widget.broadcastStream.listen((data) {
      final msg = jsonDecode(data);
      if (msg['type'] == 'message' && (msg['from'] == widget.contactUIN || msg['to'] == widget.contactUIN)) {
        if (!mounted) return;
        bool exists = _messages.any((m) => m['from'] == msg['from'] && m['to'] == msg['to'] && m['text'] == msg['text']);
        if (!exists) {
          try { _messagePlayer.play(AssetSource('sounds/01_message.mp3')); } catch(e) {}
          setState(() { _messages.add(Map<String, dynamic>.from(msg)); });
        }
      } else if (msg['type'] == 'history') {
        if (!mounted) return;
        final historyData = msg['text'];
        if (historyData != null && historyData != 'null') {
          setState(() { _messages = (jsonDecode(historyData) as List).map((m) => Map<String, dynamic>.from(m)).toList(); });
        }
      }
    });
  }

  @override
  void dispose() { _messageController.dispose(); super.dispose(); }

  void _sendMessage() {
    if (_messageController.text.isEmpty) return;
    final message = {'type': 'message', 'from': widget.myUIN, 'to': widget.contactUIN, 'text': _messageController.text, 'timestamp': DateTime.now().toIso8601String()};
    widget.channel.sink.add(jsonEncode(message));
    setState(() { _messages.add(message); _messageController.clear(); _showEmoji = false; });
  }

  String _formatTime(String? timestamp) {
    if (timestamp == null) return '';
    try {
      final dt = DateTime.parse(timestamp);
      return '${dt.day.toString().padLeft(2, '0')}.${dt.month.toString().padLeft(2, '0')}.${dt.year} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (e) { return timestamp; }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.green[700],
        title: Row(children: [
          CircleAvatar(backgroundColor: Colors.white, child: Icon(Icons.person, color: Colors.green[700])),
          const SizedBox(width: 10),
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(widget.contactName, style: const TextStyle(fontWeight: FontWeight.bold)), Text('UIN: ${widget.contactUIN}', style: const TextStyle(fontSize: 12))]),
          const Spacer(),
          IconButton(icon: const Icon(Icons.videocam), onPressed: () {}),
          IconButton(icon: const Icon(Icons.phone), onPressed: () {}),
          IconButton(icon: const Icon(Icons.person_add), onPressed: () {}),
          PopupMenuButton<String>(icon: const Icon(Icons.menu), onSelected: (value) { if (value == 'archive') _showArchive(); }, itemBuilder: (context) => [
            const PopupMenuItem(value: 'message', child: Text('Отправить сообщение')),
            const PopupMenuItem(value: 'call', child: Text('Позвонить')),
            const PopupMenuItem(value: 'file', child: Text('Отправить файл')),
            const PopupMenuItem(value: 'archive', child: Text('Архив сообщений')),
            const PopupMenuItem(value: 'profile', child: Text('Анкета')),
          ]),
        ]),
      ),
      body: Column(children: [
        Expanded(child: Container(color: Colors.grey[100], child: _messages.isEmpty ? const Center(child: Text('Нет сообщений. Начните разговор!')) : ListView.builder(padding: const EdgeInsets.all(8), itemCount: _messages.length, itemBuilder: (context, index) => _buildMessageBubble(_messages[index], _messages[index]['from'] == widget.myUIN)))),
        if (_showEmoji) Container(height: 200, color: Colors.white, child: GridView.builder(padding: const EdgeInsets.all(8), gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 8, mainAxisSpacing: 4, crossAxisSpacing: 4), itemCount: _emojis.length, itemBuilder: (context, index) => GestureDetector(onTap: () { _messageController.text += _emojis[index]; }, child: Center(child: Text(_emojis[index], style: const TextStyle(fontSize: 24)))))),
        Container(padding: const EdgeInsets.all(8), decoration: BoxDecoration(color: Colors.white, border: Border(top: BorderSide(color: Colors.grey[300]!))), child: Row(children: [
          IconButton(icon: const Icon(Icons.emoji_emotions, color: Colors.green), onPressed: () => setState(() => _showEmoji = !_showEmoji)),
          Expanded(child: TextField(controller: _messageController, decoration: const InputDecoration(hintText: 'Напишите здесь ваше сообщение...', border: OutlineInputBorder()), onSubmitted: (_) => _sendMessage(), maxLines: 3, minLines: 1)),
          const SizedBox(width: 8),
          TextButton(onPressed: () {}, child: const Text('SMS', style: TextStyle(color: Colors.grey))),
          ElevatedButton(onPressed: _sendMessage, style: ElevatedButton.styleFrom(backgroundColor: Colors.green), child: const Text('Отправить')),
          IconButton(icon: const Icon(Icons.attach_file, color: Colors.grey), onPressed: () {}),
        ])),
      ]),
    );
  }

   Widget _buildMessageBubble(Map<String, dynamic> msg, bool isMe) {
    final time = _formatTime(msg['timestamp']);
    final senderName = isMe ? 'Вы' : widget.contactName;
    
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: isMe ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Аватарка для входящих сообщений
          if (!isMe) ...[
            CircleAvatar(
              radius: 18,
              backgroundColor: Colors.green[200],
              child: Text(
                widget.contactAvatar,
                style: const TextStyle(fontSize: 18),
              ),
            ),
            const SizedBox(width: 8),
          ],
          
          // Пузырь сообщения
          Flexible(
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: isMe ? Colors.green[100] : Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.grey[300]!),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        senderName,
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        time,
                        style: TextStyle(color: Colors.grey[600], fontSize: 11),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(msg['text'] ?? '', style: const TextStyle(fontSize: 14)),
                ],
              ),
            ),
          ),
          
          // Аватарка для исходящих сообщений
          if (isMe) ...[
            const SizedBox(width: 8),
            CircleAvatar(
              radius: 18,
              backgroundColor: Colors.blue[200],
              child: Text(
                _myAvatar ?? '😀',
                style: const TextStyle(fontSize: 18),
              ),
            ),
          ],
        ],
      ),
    );
  }

  void _showArchive() {
    showDialog(context: context, builder: (context) => Dialog(child: Container(width: 600, height: 500, padding: const EdgeInsets.all(16), child: Column(children: [
      Row(children: [const Text('Архив сообщений', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)), const Spacer(), IconButton(icon: const Icon(Icons.close), onPressed: () => Navigator.pop(context))]),
      const Divider(),
      Expanded(child: ListView.builder(itemCount: _messages.length, itemBuilder: (context, index) {
        final msg = _messages[index];
        return ListTile(title: Text('${_formatTime(msg['timestamp'])} ${msg['from'] == widget.myUIN ? 'Вы' : widget.contactName}'), subtitle: Text(msg['text'] ?? ''));
      })),
    ]))));
  }
}