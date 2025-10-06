import asyncio
import logging
import os
from telethon import TelegramClient, events
from telethon.tl.types import InputPeerUser
from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN,
    DOWNLOAD_TIMEOUT,
    DOWNLOADER_BOT_USERNAME,
    DAILY_DOWNLOAD_LIMIT,
)
from utils import TempFileManager, BotError, logger
from database import Database

# Loglama ayarları
logging.basicConfig(level=logging.INFO)

# Userbot istemcisi oluşturma
userbot = TelegramClient('userbot_session', API_ID, API_HASH)

# Veritabanı bağlantısı
db = Database()

# İndirme durumlarını takip etmek için sözlük
download_tasks = {}

async def init_bot():
{{ ... }}
        await TempFileManager.cleanup_temp_files()
        if userbot.is_connected():
            await userbot.disconnect()
        logger.info("Userbot kapatıldı.")
    except Exception as e:
        logger.error(f"Temizlik sırasında hata: {str(e)}")

async def download_audio(query: str, user_id: int) -> str:
    """
    Verilen sorgudan müzik aratır, ilk sonucu indirir ve dosya yolunu döndürür.
    
    Args:
        query: Müzik adı veya YouTube linki
        user_id: İndirme yapan kullanıcının ID'si
        
    Returns:
        str: İndirilen müzik dosyasının yolu
    """
{{ ... }}
        # İndirme işlemini başlat
        async with userbot.conversation(bot_entity, timeout=DOWNLOAD_TIMEOUT) as conv:
            # Arama yap
            await conv.send_message(query)
            
            # İlk yanıtı al (arama sonuçları veya indirme başlıyor)
            try:
                response = await conv.get_response(timeout=10)
                
                # Eğer arama sonucu yoksa veya hata varsa
                if any(keyword in response.text.lower() for keyword in ['bulunamadı', 'hata', 'error', 'not found']):
                    raise BotError("Arama sonucu bulunamadı. Lütfen farklı bir arama terimi deneyin.")
                
                # Eğer seçenekler sunulduysa ilkini seç (genellikle 1 numara)
                if any(char in response.text for char in ['1', '2', '3', '4', '5']):
                    await conv.send_message('1')
                    # Seçim yanıtını bekle
                    response = await conv.get_response(timeout=10)
                
                # İndirme başlangıcını bekle
                response = await conv.get_response(timeout=30)
                
                # Müzik dosyasını bulana kadar bekle (en fazla 3 deneme)
                max_attempts = 3
                attempts = 0
                
                while attempts < max_attempts:
                    if response.media:
                        # Dosyayı indir
                        temp_file = await TempFileManager.generate_temp_filename(extension='mp3')
                        await userbot.download_media(response.media, file=temp_file)
                        
                        # Dosya boyutu kontrolü
                        if os.path.exists(temp_file) and os.path.getsize(temp_file) > 1024:  # 1KB'den büyükse
                            # İndirme sayacını güncelle
                            await db.increment_download_count(user_id)
                            
                            # İndirme geçmişine ekle
                            file_name = f"{getattr(response, 'file', {}).get('name', 'indirilen_muzik')}.mp3"
                            await db.add_to_history(user_id, file_name)
                            
                            return temp_file
                        
                        # Geçersiz dosyayı sil
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    
                    # Sonraki mesajı al
                    try:
                        response = await conv.get_response(timeout=30)
                    except asyncio.TimeoutError:
                        break
                        
                    attempts += 1
                
                # Eğer döngüden çıkıldıysa ve dosya bulunamadıysa
                raise BotError("Müzik dosyası alınamadı. Lütfen daha sonra tekrar deneyin.")
                
{{ ... }}
                raise BotError("İşlem zaman aşımına uğradı. Lütfen daha sonra tekrar deneyin.")
            
    except Exception as e:
        logger.error(f"Müzik indirilirken beklenmeyen hata: {str(e)}", exc_info=True)
        if not isinstance(e, BotError):
            raise BotError(f"Müzik indirilirken bir hata oluştu: {str(e)}")
        raise

@userbot.on(events.NewMessage(incoming=True, from_users=OWNER_ID))
async def handle_owner_message(event):
    """Bot sahibinden gelen mesajları işler."""
    try:
        if event.message.text.startswith('/'):
            command = event.message.text.split()[0].lower()
            
            if command == '/stats':
                # İstatistikleri göster
                stats = await db.get_download_stats(event.sender_id)
                await event.reply(f"Günlük indirme: {stats[0]}/{DAILY_DOWNLOAD_LIMIT}")
                
            elif command == '/premium' and len(event.message.text.split()) > 1:
                # Premium durumunu güncelle
                try:
                    user_id = int(event.message.text.split()[1])
                    status = event.message.text.split()[2].lower() == 'true'
                    await db.set_premium_status(user_id, status)
                    await event.reply(f"Premium durumu güncellendi: {status}")
                except (IndexError, ValueError):
                    await event.reply("Kullanım: /premium <user_id> <true/false>")
    except Exception as e:
        logger.error(f"Sahip komutu işlenirken hata: {e}")
        await event.reply(f"Bir hata oluştu: {e}")

async def main():
    """Ana uygulama döngüsü."""
    try:
        await init_bot()
        logger.info("Userbot çalışıyor. Çıkmak için CTRL+C tuşlarına basın.")
        
        # Botun çalışmasını sürdürmesi için sonsuz döngü
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Kullanıcı tarafından durduruldu.")
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {e}")
    finally:
        await cleanup()

if __name__ == "__main__":
    asyncio.run(main())
