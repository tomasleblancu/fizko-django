"""
SeleniumDriver optimizado para Django/Docker con Chromium.
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import logging
import os
from typing import Optional, Any
from django.conf import settings

logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    """Error personalizado para timeouts"""
    pass


class SeleniumDriver:
    """Driver de Selenium optimizado para Django/Docker con Chromium"""
    
    DEFAULT_TIMEOUT = 15
    LONG_TIMEOUT = 30
    QUICK_TIMEOUT = 5
    
    def __init__(self, headless: bool = None):
        self.driver = None
        self.wait = None
        
        # Usar configuración de Django settings si está disponible
        if headless is None:
            headless = getattr(settings, 'HEADLESS_BROWSER', True)
        
        self.headless = headless
        self._last_error: Optional[str] = None

    def _get_chrome_options(self) -> Options:
        """Obtiene las opciones básicas para Chrome"""
        options = Options()
        
        if self.headless:
            options.add_argument("--headless=new")
        
        # Detectar ambiente Docker
        is_docker = (
            os.getenv('DOCKER_ENV') is not None or
            os.path.exists('/.dockerenv') or
            os.getenv('DOCKER_CONTAINER') is not None
        )
        
        # Opciones comunes para todos los ambientes
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--window-size=1280,720")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-web-security")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")
        
        # Opciones específicas para Docker
        if is_docker:
            options.add_argument("--disable-field-trial-config")
            options.add_argument("--disable-ipc-flooding-protection")
            options.add_argument("--single-process")
            options.add_argument("--disable-setuid-sandbox")
            options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        
        # Configurar ruta del binario Chrome desde Django settings o variables de entorno
        chrome_binary = getattr(settings, 'CHROME_BINARY_PATH', None) or os.getenv('CHROME_BINARY_PATH')
        
        if chrome_binary and os.path.exists(chrome_binary):
            options.binary_location = chrome_binary
            logger.info(f"Using Chrome binary from config: {chrome_binary}")
        elif is_docker:
            # En Docker, usar chromium instalado por apt
            docker_chrome_paths = [
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser", 
                "/usr/bin/google-chrome",
                "/usr/bin/chrome"
            ]
            
            for path in docker_chrome_paths:
                if os.path.exists(path):
                    options.binary_location = path
                    logger.info(f"Found Chrome binary in Docker: {path}")
                    break
        
        return options

    def start(self) -> None:
        """Inicia el driver de forma simple"""
        if self.driver is not None:
            return
        
        logger.info(f"🚀 Iniciando SeleniumDriver para SII")
        
        try:
            options = self._get_chrome_options()
            
            # Detectar ambiente Docker
            is_docker = (
                os.getenv('DOCKER_ENV') is not None or
                os.path.exists('/.dockerenv') or
                os.getenv('DOCKER_CONTAINER') is not None
            )
            
            service = None
            
            # Buscar ChromeDriver del sistema primero
            driver_path = getattr(settings, 'CHROME_DRIVER_PATH', None) or os.getenv('CHROME_DRIVER_PATH')
            
            if driver_path and os.path.exists(driver_path):
                service = Service(driver_path)
                logger.info(f"Using ChromeDriver from config: {driver_path}")
            elif is_docker:
                # En Docker, buscar en rutas estándar
                docker_driver_paths = [
                    "/usr/bin/chromedriver",
                    "/usr/lib/chromium-browser/chromedriver",
                    "/usr/lib/chromium/chromedriver",
                ]
                
                for path in docker_driver_paths:
                    if os.path.exists(path) and os.access(path, os.X_OK):
                        service = Service(path)
                        logger.info(f"Found ChromeDriver in Docker: {path}")
                        break
            
            # Fallback a webdriver-manager si no se encontró del sistema
            if service is None:
                try:
                    logger.info("Using webdriver-manager for ChromeDriver")
                    chromedriver_path = ChromeDriverManager().install()
                    service = Service(chromedriver_path)
                    logger.info(f"webdriver-manager provided: {chromedriver_path}")
                except Exception as e:
                    logger.error(f"webdriver-manager failed: {e}")
                    raise Exception("No valid ChromeDriver found")
            
            # Inicializar driver
            self.driver = webdriver.Chrome(service=service, options=options)
            self.wait = WebDriverWait(self.driver, self.DEFAULT_TIMEOUT)
            
            # Configurar timeouts
            self.driver.set_page_load_timeout(30)
            self.driver.implicitly_wait(5)
            
            logger.info(f"✅ SeleniumDriver iniciado exitosamente")
            
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"❌ Error al iniciar driver: {e}")
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            self.driver = None
            self.wait = None
            raise

    def quit(self) -> None:
        """Cierra el driver"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info(f"🔴 SeleniumDriver cerrado exitosamente")
            except Exception as e:
                logger.warning(f"⚠️ Error al cerrar driver: {e}")
            finally:
                self.driver = None
                self.wait = None

    def wait_for_element(self, by: str, value: str, timeout: Optional[int] = None) -> Any:
        """Espera a que un elemento esté presente"""
        if not self.driver:
            raise Exception("Driver no está iniciado")
        try:
            wait = WebDriverWait(self.driver, timeout or self.DEFAULT_TIMEOUT)
            return wait.until(EC.presence_of_element_located((by, value)))
        except TimeoutException as e:
            self._last_error = f"Timeout esperando elemento {value}"
            logger.error(f"Timeout esperando elemento {value}: {e}")
            raise

    def wait_for_clickable(self, by: str, value: str, timeout: Optional[int] = None) -> Any:
        """Espera a que un elemento sea clickeable"""
        if not self.driver:
            raise Exception("Driver no está iniciado")
        try:
            wait = WebDriverWait(self.driver, timeout or self.DEFAULT_TIMEOUT)
            return wait.until(EC.element_to_be_clickable((by, value)))
        except TimeoutException as e:
            self._last_error = f"Timeout esperando elemento clickeable {value}"
            logger.error(f"Timeout esperando elemento clickeable {value}: {e}")
            raise

    def wait_for_elements(self, by: str, value: str, timeout: Optional[int] = None) -> list:
        """Espera a que múltiples elementos estén presentes"""
        if not self.driver:
            raise Exception("Driver no está iniciado")
        try:
            wait = WebDriverWait(self.driver, timeout or self.DEFAULT_TIMEOUT)
            return wait.until(EC.presence_of_all_elements_located((by, value)))
        except TimeoutException as e:
            self._last_error = f"Timeout esperando elementos {value}"
            logger.error(f"Timeout esperando elementos {value}: {e}")
            raise

    def select_option_by_value(self, select_element: Any, value: str) -> None:
        """Selecciona una opción en un dropdown por su valor"""
        from selenium.webdriver.support.ui import Select
        try:
            select = Select(select_element)
            select.select_by_value(value)
        except Exception as e:
            self._last_error = f"Error seleccionando opción {value}"
            logger.error(f"Error seleccionando opción {value}: {e}")
            raise

    def get_last_error(self) -> Optional[str]:
        """Retorna el último error ocurrido"""
        return self._last_error

    def get_page_source(self) -> str:
        """Obtiene el código fuente de la página actual"""
        if not self.driver:
            raise Exception("Driver no está iniciado")
        return self.driver.page_source

    def get_current_url(self) -> str:
        """Obtiene la URL actual"""
        if not self.driver:
            raise Exception("Driver no está iniciado")
        return self.driver.current_url

    def execute_script(self, script: str, *args: Any) -> Any:
        """Ejecuta un script JavaScript en la página"""
        if not self.driver:
            raise Exception("Driver no está iniciado")
        try:
            return self.driver.execute_script(script, *args)
        except Exception as e:
            self._last_error = f"Error ejecutando script: {script}"
            logger.error(f"Error ejecutando script: {e}")
            raise

    # Context manager
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.quit()