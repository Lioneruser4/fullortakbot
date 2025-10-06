import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor

from config import BOT_TOKEN, OWNER_ID, DAILY_DOWNLOAD_LIMIT, TEMP_DIR
from database import Database
from utils import TempFileManager, BotError, is_valid_url, format_file_size, logger

# Bot ve dispatcher ayarları
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Veritabanı bağlantısını oluştur
try:
    db = Database()
    logger.info("Veritabanı bağlantısı başlatıldı")
except Exception as e:
    logger.error(f"Veritabanı bağlantı hatası: {str(e)}")
    raise

# Durumlar
class DownloadStates(StatesGroup):
    waiting_for_link = State()

# Yardımcı fonksiyonlar
def is_owner(user_id: int) -> bool:
    """Kullanıcının bot sahibi olup olmadığını kontrol eder."""
    return user_id == OWNER_ID

async def delete_temp_file(file_path: str):
    """Geçici dosyayı siler."""
    try:
        if os.path.exists(file_path):
            logger.info(f"Geçici dosya silindi: {file_path}")
    except Exception as e:
        logger.error(f"Dosya silinirken hata: {e}")

# Komut işleyicileri
@dp.message_handler(chat_type=types.ChatType.PRIVATE, content_types=types.ContentTypes.TEXT)
async def private_chat_handler(message: types.Message, state: FSMContext):
    """Handles private chat messages."""
    # Eğer mesaj bir komut değilse, doğrudan işleme al
    # If the message is not a command, redirect it to the music download process
    if not message.text.startswith('/'):
        await process_music_request(message, message.text)
    else:
        # If the message is a command, handle it accordingly
        if message.text.startswith('/song'):
            args = message.get_args()
            if args:
                await process_music_request(message, args)
            else:
                await message.answer(
                    "Usage: /song <song name or YouTube link>\n"
                    "Example: /song Daft Punk - Get Lucky"
                )

@dp.message_handler(state=DownloadStates.waiting_for_link)
async def process_music_request(message: types.Message, state: FSMContext):
    """Handles user's music request (link or song name)."""
    user_input = message.text.strip()
{{ ... }}
    
    # Kullanıcının indirme hakkı var mı kontrol et
    if not await db.can_download(user_id):
        await state.finish()
        await message.answer(
            "❌ Günlük indirme limitiniz doldu.\n"
            f"Günlük limit: {DAILY_DOWNLOAD_LIMIT} şarkı\n"
            "Yarın tekrar deneyebilir veya premium üye olabilirsiniz."
        )
        return
    
    # Kullanıcıya işlemin başladığını bildir
    processing_msg = await message.answer("⏳ Müzik aranıyor, lütfen bekleyin...")
    
    try:
        # Müziği indir
        from bridge_userbot import download_audio
        
        # Kullanıcıya işlem durumunu güncelle
        await processing_msg.edit_text("🔍 Müzik bulunuyor...")
        
        # Müziği indir
        temp_file = await download_audio(user_input, user_id)
        
        if not os.path.exists(temp_file) or os.path.getsize(temp_file) < 1024:  # 1KB'den küçükse geçersiz
            raise BotError("Geçersiz müzik dosyası alındı. Lütfen farklı bir şarkı deneyin.")
        
        # Kullanıcıya dosya gönderiliyor bilgisi
        await processing_msg.edit_text("📤 Müzik yükleniyor...")
        
        # Dosya adını düzenle (özel karakterleri kaldır)
        safe_filename = ''.join(c if c.isalnum() or c in ' ._-' else '_' for c in os.path.basename(temp_file))
        
        # Dosyayı gönder
        with open(temp_file, 'rb') as audio_file:
            await message.answer_audio(
                audio_file,
                title=safe_filename.replace('.mp3', ''),
                performer="FullSong Bot",
                caption=f"🎵 {safe_filename}\n\n@FullSongBot ile indirildi"
            )
        
        # Başarı mesajı
        file_size = os.path.getsize(temp_file)
        await message.answer(
            "✅ Müzik başarıyla indirildi!\n"
            f"📁 Boyut: {format_file_size(file_size)}\n"
            "Başka bir şarkı indirmek için /download yazabilirsiniz."
        )
        
    except BotError as e:
        await message.answer(f"❌ Hata: {e.user_friendly}")
        logger.error(f"Müzik indirilirken hata: {str(e)}")
    except Exception as e:
        error_msg = f"❌ Bir hata oluştu: {str(e)}. Lütfen daha sonra tekrar deneyin."
        await message.answer(error_msg)
        logger.error(f"Beklenmeyen hata: {str(e)}", exc_info=True)
    finally:
        # Geçici dosyayı sil
        if 'temp_file' in locals() and temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
                logger.info(f"Geçici dosya silindi: {temp_file}")
            except Exception as e:
                logger.error(f"Dosya silinirken hata: {e}")
        
        # İşlemi sonlandır
        try:
            await processing_msg.delete()
        except:
            pass
            
        await state.finish()

@dp.message_handler(commands=['stats'])
async def show_stats(message: types.Message):
    """Kullanıcının indirme istatistiklerini gösterir."""
    user_id = message.from_user.id
    is_premium = await db.is_premium(user_id)
    daily_downloads, last_download = await db.get_download_stats(user_id)
    
    stats_text = (
        f"📊 <b>İstatistikleriniz</b>\n"
        f"🎯 Durum: {'🌟 Premium' if is_premium else '🔹 Standart'}\n"
        f"📥 Bugünkü İndirme: {daily_downloads}/{DAILY_DOWNLOAD_LIMIT}\n"
        f"⏱ Son İndirme: {last_download if last_download else 'Henüz yok'}"
    )
    
    await message.answer(stats_text)

@dp.message_handler(commands=['premium'])
async def premium_info(message: types.Message):
    """Premium üyelik bilgilerini gösterir."""
    premium_text = (
        "🌟 <b>Premium Üyelik Avantajları</b>\n\n"
        "• Sınırsız müzik indirme\n"
        "• Öncelikli destek\n"
        "• Reklamsız deneyim\n"
        "• Yeni özelliklere erken erişim\n\n"
        "Premium üye olmak için @kullaniciadı ile iletişime geçin."
    )
    
    await message.answer(premium_text)

# Yönetici komutları
@dp.message_handler(commands=['admin'], is_chat_admin=True)
async def admin_commands(message: types.Message):
    """Yönetici komutlarını gösterir."""
    if not is_owner(message.from_user.id):
        return
    
    admin_text = (
        "👑 <b>Yönetici Komutları</b>\n\n"
        "/stats <user_id> - Kullanıcı istatistikleri\n"
        "/premium <user_id> <on/off> - Premium durumunu değiştir\n"
        "/broadcast - Tüm kullanıcılara mesaj gönder"
    )
    
    await message.answer(admin_text)

# Hata yönetimi
@dp.errors_handler()
async def errors_handler(update: types.Update, exception: Exception):
    """Global hata yönetimi."""
    logger.error(f"Hata oluştu: {exception}", exc_info=True)
    
    if isinstance(update, types.Message):
        try:
            await update.answer("❌ Bir hata oluştu. Lütfen daha sonra tekrar deneyin.")
        except:
            pass
    
    return True

# Bot başlatma
async def on_startup(dp):
    """Bot başlatıldığında çalışır."""
    await TempFileManager.create_temp_dir()
    await bot.send_message(OWNER_ID, "🤖 Bot başarıyla başlatıldı!")
    logger.info("Bot başlatıldı.")

async def on_shutdown(dp):
    """Bot kapatıldığında çalışır."""
    try:
        # Veritabanı bağlantısını kapat
        await db.close()
        logger.info("Veritabanı bağlantısı kapatıldı")
        
        # Bot'u kapat
        await bot.close()
        await dp.storage.close()
        await dp.storage.wait_closed()
        logger.info("Bot başarıyla kapatıldı")
    except Exception as e:
        logger.error(f"Bot kapatılırken hata: {str(e)}")
        raise

if __name__ == '__main__':
    try:
        # Event loop'u al
        loop = asyncio.get_event_loop()
        
        # Bot'u başlat
        logger.info("Bot başlatılıyor...")
        executor.start_polling(dp, 
                            skip_updates=True,
                            on_startup=on_startup,
                            on_shutdown=on_shutdown)
    except KeyboardInterrupt:
        logger.info("Bot kullanıcı tarafından durduruldu")
    except Exception as e:
        logger.error(f"Bot çalışırken beklenmeyen hata: {str(e)}")
    finally:
        # Tüm bekleyen görevleri iptal et
        try:
            loop = asyncio.get_event_loop()
            pending = asyncio.all_tasks(loop=loop)
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
        except Exception as e:
            logger.error(f"Loop kapatılırken hata: {str(e)}")
