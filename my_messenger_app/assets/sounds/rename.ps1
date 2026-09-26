# Переименование основных файлов
Rename-Item -Path "message.mp3" -NewName "01_message.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "login.mp3" -NewName "02_login.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "online.mp3" -NewName "03_user_online.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "startup.mp3" -NewName "04_startup.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "email.mp3" -NewName "07_mail.mp3" -ErrorAction SilentlyContinue

# Остальные файлы
Rename-Item -Path "icq-incoming-file.mp3" -NewName "05_file_received.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "icq-incoming-notification.mp3" -NewName "06_notification.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "icq-mail.mp3" -NewName "07_mail.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "icq-music-on-startup.mp3" -NewName "08_music_startup.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "icq-oh-oh-with-echo.mp3" -NewName "09_oh_oh_echo.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "icq-remix.mp3" -NewName "10_remix.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "icq-ringtone.mp3" -NewName "11_ringtone.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "icq-sms.mp3" -NewName "12_sms.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "icq-sound-but-a-little-slower.mp3" -NewName "13_sound_slower.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "icq-sound-option.mp3" -NewName "14_sound_option.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "icq-standard-plus-female-voice.mp3" -NewName "15_female_voice.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "incoming-sms-message-via-icq.mp3" -NewName "16_incoming_sms.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "melodious-notification-sound.mp3" -NewName "17_melodious.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "oh-oh-icq-sound.mp3" -NewName "18_oh_oh.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "single-sound-message-icq-ooh.mp3" -NewName "19_single_ooh.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "sound-for-crazy-people.mp3" -NewName "20_crazy.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "the-sound-of-knocking-on-the-door.mp3" -NewName "21_knock.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "wild-music-for-sms.mp3" -NewName "22_wild_sms.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "epic-notification-about-adding-a-contact.mp3" -NewName "23_contact_added.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "icq-6-notification-sound.mp3" -NewName "24_icq6.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "icq-6-surround-call.mp3" -NewName "25_surround_call.mp3" -ErrorAction SilentlyContinue
Rename-Item -Path "icq-modern-notification-sound.mp3" -NewName "26_modern.mp3" -ErrorAction SilentlyContinue

Write-Host "✅ Все файлы переименованы!" -ForegroundColor Green