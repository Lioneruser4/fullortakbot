import os
import logging
from datetime import datetime
from typing import Optional
import aiofiles
import aiofiles.os
from config import TEMP_DIR

# Loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Geçici dosya yöneticisi
class TempFileManager:
    @staticmethod
    async def create_temp_dir():
        """Geçici klasör yoksa oluşturur."""
        try:
            if not await aiofiles.os.path.exists(TEMP_DIR):
                await aiofiles.os.mkdir(TEMP_DIR)
                logger.info(f"Geçici klasör oluşturuldu: {TEMP_DIR}")
        except Exception as e:
            logger.error(f"Geçici klasör oluşturulurken hata: {e}")
            raise

    @staticmethod
    async def generate_temp_filename(extension: str = 'mp3') -> str:
        """Rastgele bir geçici dosya adı oluşturur."""
        timestamp = int(datetime.now().timestamp())
        random_str = os.urandom(4).hex()
        return os.path.join(TEMP_DIR, f"temp_{timestamp}_{random_str}.{extension}")

    @staticmethod
    async def cleanup_temp_files():
        """Geçici klasördeki tüm dosyaları siler."""
        try:
            if not await aiofiles.os.path.exists(TEMP_DIR):
                return
                
            async for filename in aiofiles.os.scandir(TEMP_DIR):
                try:
                    if filename.is_file():
                        await aiofiles.os.remove(filename.path)
                except Exception as e:
                    logger.error(f"{filename} silinirken hata: {e}")
            
            logger.info("Geçici dosyalar temizlendi.")
        except Exception as e:
            logger.error(f"Geçici dosyalar temizlenirken hata: {e}")

# Hata yönetimi
class BotError(Exception):
    """Özel hata sınıfı"""
    def __init__(self, message: str, user_friendly: str = None):
        self.message = message
        self.user_friendly = user_friendly or "Bir hata oluştu. Lütfen daha sonra tekrar deneyin."
        super().__init__(self.message)

# Format dönüştürücüler
def format_duration(seconds: int) -> str:
    """Saniyeyi dakika:saniye formatına çevirir."""
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes}:{seconds:02d}"

def format_file_size(size_bytes: int) -> str:
    """Dosya boyutunu okunabilir formata çevirir."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

# Kullanıcı giriş doğrulama
def is_valid_url(url: str) -> bool:
    """Verilen metnin geçerli bir URL olup olmadığını kontrol eder."""
    import re
    url_pattern = re.compile(
        r'^(https?:\/\/)?'  # http:// veya https://
        r'((([a-z\d]([a-z\d-]*[a-z\d])*)\.)+[a-z]{2,}|'  # domain
        r'((\d{1,3}\.){3}\d{1,3}))'  # veya IPv4
        r'(\:\d+)?(\/[-a-z\d%_.~+]*)*'  # port ve path
        r'(\?[;&a-z\d%_.~+=-]*)?'  # query string
        r'(\#[-a-z\d_]*)?$', re.IGNORECASE)  # fragment
    return bool(re.match(url_pattern, url))
