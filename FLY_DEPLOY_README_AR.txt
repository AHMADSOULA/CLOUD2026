إعداد Fly.io للبوت

1) ارفع محتويات هذا المجلد إلى جذر مستودع GitHub.
2) افتح fly.toml وغيّر app إلى اسم فريد بحروف إنجليزية صغيرة وأرقام وشرطات فقط.
3) في Fly.io اختر Launch an App ثم Launch from GitHub واختر المستودع.
4) تأكد أن Fly يستخدم Dockerfile الموجود في جذر المستودع.
5) بعد إنشاء التطبيق، أضف BOT_TOKEN من صفحة Secrets في لوحة Fly.io. لا تضعه في GitHub.
6) شغّل Deploy وراقب Logs. يجب أن يظهر سجل تشغيل البوت دون أخطاء.

ملاحظات:
- هذا تطبيق Telegram polling وليس موقع ويب؛ لذلك fly.toml لا يعرّف http_service أو منفذ HTTP.
- Dockerfile مبني على صورة Microsoft Playwright Python 1.48.0 مع Chromium.
- قاعدة البيانات الافتراضية في /tmp/bot.db مؤقتة وقد تضيع عند استبدال الآلة أو إعادة النشر. لإبقائها دائمة، أنشئ Fly Volume واربطه إلى /data ثم عيّن DB_PATH=/data/bot.db في إعدادات التطبيق.
- لا ترفع .env أو التوكن أو ملفات الجلسات وCookies إلى GitHub.
