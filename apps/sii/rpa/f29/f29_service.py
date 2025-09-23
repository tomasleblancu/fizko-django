"""
Servicio F29 para manejo de formularios tributarios
Migrado y adaptado desde legacy fizko-backend
"""
import os
import csv
import logging
import time
from typing import Dict, List, Optional, Any
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from ..sii_rpa_service import RealSIIService
from .f29_types import (
    SubtablaF29, FilaDatos, ValorFila, ColumnasSubtabla,
    CampoF29, DetalleF29, ResumenF29, EventoHistorialF29, FormularioF29
)
from ...utils.exceptions import SIIValidationError

logger = logging.getLogger(__name__)


class F29Service:
    """
    Servicio principal para manejo de formularios F29.
    Integra con el RPA existente de manera modular.
    """

    def __init__(self, tax_id: str, password: str, headless: bool = True):
        self.tax_id = tax_id
        self.password = password
        self.headless = headless
        self._rpa_service = None
        self._f29_rpa = None

    def _get_rpa_service(self) -> RealSIIService:
        """Obtiene o crea la instancia del servicio RPA base"""
        if not self._rpa_service:
            self._rpa_service = RealSIIService(
                tax_id=self.tax_id,
                password=self.password,
                headless=self.headless
            )
        return self._rpa_service

    def _get_f29_rpa(self, folio: str) -> 'F29RpaService':
        """Obtiene o crea la instancia del servicio F29 RPA"""
        if not self._f29_rpa:
            rpa_service = self._get_rpa_service()
            self._f29_rpa = F29RpaService(rpa_service, folio)
        return self._f29_rpa

    def obtener_formulario_f29(self, folio: str, periodo: str = None) -> Dict[str, Any]:
        """
        Obtiene los datos completos de un formulario F29.

        Args:
            folio: Folio del formulario F29
            periodo: Período tributario (opcional)

        Returns:
            Dict con los datos completos del F29
        """
        try:
            logger.info(f"🔍 Obteniendo F29 folio: {folio}")

            # Autenticar con SII
            rpa_service = self._get_rpa_service()
            if not rpa_service.authenticate(force_auth=True):
                raise SIIValidationError("Error en autenticación con SII")

            # Crear servicio F29 específico
            f29_rpa = F29RpaService(rpa_service, folio, periodo)

            # Navegar al formulario
            f29_rpa.navegar_a_formulario()

            # Obtener datos del formulario
            campos_extraidos = f29_rpa.extraer_valores_por_xpath()

            return {
                'status': 'success',
                'folio': folio,
                'periodo': periodo,
                'campos_extraidos': campos_extraidos,
                'total_campos': len(campos_extraidos),
                'extraction_method': 'f29_rpa',
                'timestamp': time.time()
            }

        except Exception as e:
            logger.error(f"❌ Error obteniendo F29 {folio}: {str(e)}")
            return {
                'status': 'error',
                'folio': folio,
                'message': str(e),
                'extraction_method': 'f29_rpa_failed',
                'timestamp': time.time()
            }

    def obtener_formularios_periodo(self, periodo: str) -> List[Dict[str, Any]]:
        """
        Obtiene todos los formularios F29 de un período específico.

        Args:
            periodo: Período en formato YYYYMM

        Returns:
            Lista de formularios F29 del período
        """
        # Esta funcionalidad requeriría navegación adicional al listado
        # Por ahora, se retorna estructura base para implementación futura
        logger.info(f"📋 Listado F29 período {periodo} - Por implementar")
        return {
            'status': 'not_implemented',
            'periodo': periodo,
            'message': 'Listado de formularios por período pendiente de implementación'
        }

    def close(self):
        """Cierra las conexiones y libera recursos"""
        if self._rpa_service:
            self._rpa_service.close()
            self._rpa_service = None
        self._f29_rpa = None


class F29RpaService:
    """
    Servicio RPA específico para formularios F29.
    Migrado desde legacy RectificacionF29.
    """

    def __init__(self, rpa_service: RealSIIService, folio: str, periodo: str = None):
        self.rpa_service = rpa_service
        self.folio = folio
        self.periodo = periodo
        self._codigos_f29 = None

    @classmethod
    def buscar_formularios(
        cls,
        rpa_service: RealSIIService,
        codigo_formulario: str = "29",
        anio: Optional[str] = None,
        mes: Optional[str] = None,
        folio: Optional[str] = None
    ) -> List[FormularioF29]:
        """
        Busca formularios F29 en el SII sin necesidad de folio específico.
        Migrado desde legacy buscar_formularios.

        Args:
            rpa_service: Instancia del servicio RPA base
            codigo_formulario: Código del formulario (por defecto "29" para F29)
            anio: Año a consultar (obligatorio si no se busca por folio)
            mes: Mes a consultar (opcional, solo para búsqueda por período)
            folio: Folio específico a consultar (opcional)

        Returns:
            Lista de formularios F29 encontrados

        Raises:
            ValueError: Si los parámetros no son válidos
            TimeoutException: Si hay un timeout al esperar elementos
            Exception: Para otros errores inesperados
        """
        if not rpa_service.driver:
            raise Exception("Driver no disponible")

        try:
            # Validar parámetros
            if folio:
                # Si se busca por folio, el año no es necesario
                if mes:
                    raise ValueError("No se puede especificar mes cuando se busca por folio")
            else:
                # Si no se busca por folio, el año es obligatorio
                if not anio:
                    raise ValueError("El año es obligatorio cuando no se busca por folio")
                if not anio.isdigit() or len(anio) != 4:
                    raise ValueError("El año debe ser un número de 4 dígitos")

                if mes and (not mes.isdigit() or int(mes) < 1 or int(mes) > 12):
                    raise ValueError("El mes debe ser un número entre 1 y 12")

            logger.info(f"🔍 Buscando formularios F29 - Año: {anio}, Mes: {mes}, Folio: {folio}")

            # Navegar a la página de búsqueda con retry
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"🌐 Navegando a página de búsqueda (intento {attempt + 1}/{max_retries})")
                    rpa_service.driver.driver.get("https://www4.sii.cl/sifmConsultaInternet/index.html?dest=cifxx&form=29")

                    # Esperar más tiempo para que cargue la página
                    time.sleep(2)

                    # Verificar que la página cargó
                    logger.info("📄 Verificando carga de página...")
                    page_source = rpa_service.driver.driver.page_source
                    if "Buscar Formulario" in page_source or "buscar" in page_source.lower():
                        logger.info("✅ Página de búsqueda detectada")
                        break
                    else:
                        logger.warning(f"⚠️ Página no parece haber cargado correctamente (intento {attempt + 1})")
                        if attempt < max_retries - 1:
                            time.sleep(2)
                            continue
                        else:
                            logger.error("❌ No se pudo cargar la página de búsqueda después de varios intentos")
                            # Intentar continuar de todos modos

                except Exception as e:
                    logger.warning(f"⚠️ Error navegando a página de búsqueda (intento {attempt + 1}): {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(3)
                        continue
                    else:
                        raise

            # Click en "Buscar Formulario"
            buscar_button = rpa_service.driver.wait_for_clickable(
                By.XPATH, "//button[contains(@class, 'gw-button-blue-bootstrap') and contains(text(), 'Buscar Formulario')]",
                timeout=rpa_service.driver.LONG_TIMEOUT
            )

            buscar_button.click()
            time.sleep(1)

            # Seleccionar tipo de formulario (DPS: Formularios de Impuesto)
            tipo_select = rpa_service.driver.wait_for_element(
                By.CLASS_NAME, "gwt-ListBox",
                timeout=rpa_service.driver.LONG_TIMEOUT
            )
            rpa_service.driver.select_option_by_value(tipo_select, "DPS")
            time.sleep(0.5)

            # Seleccionar código de formulario
            codigo_select = rpa_service.driver.wait_for_elements(
                By.CLASS_NAME, "gwt-ListBox",
                timeout=rpa_service.driver.LONG_TIMEOUT
            )[1]

            # Verificar que el código está disponible
            try:
                opciones_disponibles = [
                    option.get_attribute("value")
                    for option in codigo_select.find_elements(By.TAG_NAME, "option")
                ]
                logger.info(f"🔍 Opciones disponibles: {opciones_disponibles}")

                if codigo_formulario not in opciones_disponibles:
                    raise ValueError(f"Código '{codigo_formulario}' no disponible. Opciones: {opciones_disponibles}")

            except Exception as e:
                logger.warning(f"⚠️ No se pudieron obtener opciones del dropdown: {str(e)}")

            rpa_service.driver.select_option_by_value(codigo_select, codigo_formulario)
            time.sleep(0.5)

            # Seleccionar opción de búsqueda
            if folio:
                # Búsqueda por folio
                folio_radio = rpa_service.driver.wait_for_element(
                    By.XPATH, "//label[contains(text(), 'Folio')]/..//input",
                    timeout=rpa_service.driver.LONG_TIMEOUT
                )
                folio_radio.click()
                folio_input = rpa_service.driver.wait_for_element(
                    By.CLASS_NAME, "gwt-TextBox",
                    timeout=rpa_service.driver.LONG_TIMEOUT
                )
                folio_input.send_keys(folio)

            elif mes:
                # Búsqueda por período
                periodo_radio = rpa_service.driver.wait_for_element(
                    By.XPATH, "//label[contains(text(), 'Periodo')]/..//input",
                    timeout=rpa_service.driver.LONG_TIMEOUT
                )
                periodo_radio.click()
                selects = rpa_service.driver.wait_for_elements(
                    By.CLASS_NAME, "gwt-ListBox",
                    timeout=rpa_service.driver.LONG_TIMEOUT
                )
                assert anio is not None  # Ya validado arriba
                rpa_service.driver.select_option_by_value(selects[2], anio)
                rpa_service.driver.select_option_by_value(selects[3], mes)

            else:
                # Búsqueda anual
                anual_radio = rpa_service.driver.wait_for_element(
                    By.XPATH, "//label[contains(text(), 'Anual')]/..//input",
                    timeout=rpa_service.driver.LONG_TIMEOUT
                )
                anual_radio.click()
                anio_select = rpa_service.driver.wait_for_elements(
                    By.CLASS_NAME, "gwt-ListBox",
                    timeout=rpa_service.driver.LONG_TIMEOUT
                )[2]
                assert anio is not None  # Ya validado arriba
                rpa_service.driver.select_option_by_value(anio_select, anio)

            # Click en Consultar
            consultar_button = rpa_service.driver.wait_for_clickable(
                By.XPATH, "//button[contains(text(), 'Consultar')]",
                timeout=rpa_service.driver.LONG_TIMEOUT
            )
            consultar_button.click()
            time.sleep(1)

            # Obtener resultados
            resultados: List[FormularioF29] = []
            try:
                tabla = rpa_service.driver.wait_for_element(
                    By.CLASS_NAME, "gw-detalle-center-busqueda",
                    timeout=rpa_service.driver.LONG_TIMEOUT
                )
                filas = tabla.find_elements(By.TAG_NAME, "tr")[1:]  # Ignorar encabezados

                logger.info(f"📋 Encontradas {len(filas)} filas de resultados")

                for i, fila in enumerate(filas):
                    try:
                        celdas = fila.find_elements(By.TAG_NAME, "td")
                        if len(celdas) >= 7:
                            # Limpiar y convertir el monto
                            monto_texto = celdas[5].text.replace(',', '').replace('$', '').replace('.', '').strip()
                            try:
                                monto = int(monto_texto) if monto_texto.isdigit() else 0
                            except (ValueError, TypeError):
                                monto = 0

                            formulario: FormularioF29 = {
                                "folio": celdas[1].text.strip(),
                                "period": celdas[0].text.strip(),
                                "contributor": celdas[2].text.strip(),
                                "submission_date": celdas[3].text.strip(),
                                "status": celdas[4].text.strip(),
                                "amount": monto
                            }
                            resultados.append(formulario)
                            logger.debug(f"✅ Formulario {i+1}: {formulario['folio']} - {formulario['period']}")

                    except Exception as e:
                        logger.warning(f"⚠️ Error procesando fila {i+1}: {str(e)}")
                        continue

            except TimeoutException:
                logger.warning("❌ No se encontraron resultados en la tabla")

            logger.info(f"🎯 Búsqueda completada: {len(resultados)} formularios encontrados")
            return resultados

        except Exception as e:
            logger.error(f"❌ Error al buscar formularios: {str(e)}")
            raise

    def navegar_a_formulario(self):
        """Navega directamente al formulario F29"""
        try:
            url = f"https://www4.sii.cl/rfiInternet/?opcionPagina=Rect&form=29&folio={self.folio}#rfiDslFormRect"
            logger.info(f"🌐 Navegando a F29: {url}")

            self.rpa_service.driver.driver.get(url)
            time.sleep(3)  # Esperar carga del formulario

            # Verificar que el formulario cargó correctamente
            try:
                self.rpa_service.driver.driver.find_element(By.CLASS_NAME, "borde_tabla_f29")
                logger.info("✅ Formulario F29 cargado exitosamente")
            except NoSuchElementException:
                raise SIIValidationError("No se pudo cargar el formulario F29")

        except Exception as e:
            logger.error(f"❌ Error navegando a formulario F29: {str(e)}")
            raise

    def _cargar_codigos_f29(self) -> Dict[str, CampoF29]:
        """
        Carga los códigos F29 desde el archivo CSV.
        Migrado desde legacy.
        """
        if self._codigos_f29 is not None:
            return self._codigos_f29

        try:
            csv_path = os.path.join(os.path.dirname(__file__), '..', 'codigos_f29.csv')
            codigos = {}

            logger.info(f"📄 Cargando códigos F29 desde: {csv_path}")

            if not os.path.exists(csv_path):
                logger.error(f"❌ Archivo codigos_f29.csv no encontrado en {csv_path}")
                return {}

            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    codigo = row.get('code', '').strip()
                    if codigo:
                        codigos[codigo] = {
                            'name': row.get('name', '').strip(),
                            'type': row.get('type', '').strip(),
                            'task': row.get('task', '').strip(),
                            'subject': row.get('subject', '').strip(),
                            'code': codigo,
                            'xpath': row.get('xpath', '').strip()
                        }

            logger.info(f"✅ Cargados {len(codigos)} códigos F29")
            self._codigos_f29 = codigos
            return codigos

        except Exception as e:
            logger.error(f"❌ Error cargando códigos F29: {str(e)}")
            return {}

    def obtener_formulario_actual(self) -> List[SubtablaF29]:
        """
        Obtiene la estructura actual del formulario F29.
        Migrado desde legacy.
        """
        try:
            logger.info("=== PROCESANDO FORMULARIO F29 ===")

            # Buscar tabla principal del F29
            tabla_f29 = self.rpa_service.driver.driver.find_element(By.CLASS_NAME, "borde_tabla_f29")
            filas = tabla_f29.find_elements(By.TAG_NAME, "tr")

            logger.info(f"📋 {len(filas)} filas encontradas en F29")

            # Variables para procesar la estructura
            main_title = None
            subtitles = []
            column_names = None
            rows_data = []
            processed_subtables = []

            for i, fila in enumerate(filas):
                try:
                    all_cells = fila.find_elements(By.TAG_NAME, "td")
                    if not all_cells:
                        continue

                    # Identificar tipo de fila
                    left_header_cell = None
                    header_cell = None
                    column_cell = None
                    line_cell = None

                    for celda in all_cells:
                        classes = celda.get_attribute("class") or ""
                        texto = celda.text.strip()

                        if "f29_celda_cabecera_izq" in classes and texto and not left_header_cell:
                            left_header_cell = celda
                        elif "f29_celda_cabecera" in classes and texto and not header_cell:
                            header_cell = celda
                        elif "f29_celda_columna_cabecera" in classes and texto and not column_cell:
                            column_cell = celda
                        elif "celda-linea" in classes and texto and not line_cell:
                            line_cell = celda

                    # Procesar según tipo de fila
                    if left_header_cell:
                        # Subtítulo
                        subtitles.append(left_header_cell.text)

                    elif header_cell:
                        # Título principal - procesar sección anterior si existe
                        new_title = header_cell.text.strip()

                        if new_title and (main_title is None or new_title != main_title):
                            if main_title and rows_data:
                                subtabla = self._process_subtable(main_title, subtitles, column_names, rows_data)
                                processed_subtables.append(subtabla)
                                logger.info(f"✅ Subtabla '{main_title}': {len(rows_data)} filas")

                            # Nueva sección
                            main_title = new_title
                            subtitles = []
                            column_names = None
                            rows_data = []

                    elif column_cell:
                        # Encabezados de columnas
                        columns_b = [celda for celda in all_cells
                                   if "f29_celda_columna_cabecera_b" in (celda.get_attribute("class") or "")
                                   and celda.text.strip()]

                        column_names = {
                            "title": column_cell.text,
                            "columns": [col.text for col in columns_b]
                        }

                    elif line_cell:
                        # Fila de datos
                        line_number = line_cell.text
                        description = ""
                        values = []

                        # Buscar descripción y valores
                        for celda in all_cells:
                            classes = celda.get_attribute("class") or ""

                            if "f29_celda_descripcion" in classes:
                                description = celda.text.strip()
                            elif ("f29_celda_valor" in classes or
                                  "f29_celda_valor_calculado" in classes):
                                valor = celda.text.strip()
                                if valor:
                                    values.append({
                                        "code": line_number,
                                        "value": valor
                                    })

                        if line_number and description:
                            rows_data.append({
                                "line": line_number,
                                "description": description,
                                "values": values
                            })

                except Exception as e:
                    logger.warning(f"⚠️ Error procesando fila {i}: {str(e)}")
                    continue

            # Procesar última sección
            if main_title and rows_data:
                subtabla = self._process_subtable(main_title, subtitles, column_names, rows_data)
                processed_subtables.append(subtabla)
                logger.info(f"✅ Subtabla final '{main_title}': {len(rows_data)} filas")

            logger.info(f"🎯 F29 procesado: {len(processed_subtables)} subtablas")
            return processed_subtables

        except Exception as e:
            logger.error(f"❌ Error procesando F29: {str(e)}")
            raise

    def _process_subtable(self, title: str, subtitles: List[str],
                         columns: Optional[Dict], rows: List[Dict]) -> SubtablaF29:
        """Procesa una subtabla individual del F29"""
        return {
            "main_title": title,
            "subtitles": subtitles.copy(),
            "columns": columns or {"title": "", "columns": []},
            "rows": rows.copy()
        }

    def extraer_valores_por_xpath(self) -> List[ValorFila]:
        """
        Extrae valores específicos usando XPaths del CSV.
        Migrado desde legacy.
        """
        try:
            logger.info("=== EXTRAYENDO VALORES POR XPATH ===")

            campos_f29 = self._cargar_codigos_f29()
            if not campos_f29:
                logger.warning("❌ No se pudieron cargar los códigos F29")
                return []

            # Filtrar campos con XPath válido
            campos_con_xpath = {
                code: data for code, data in campos_f29.items()
                if data.get('xpath', '').strip()
            }

            logger.info(f"🎯 Extrayendo {len(campos_con_xpath)} campos con XPath")

            resultados = []
            for code, campo in campos_con_xpath.items():
                try:
                    xpath = campo['xpath']
                    element = self.rpa_service.driver.driver.find_element(By.XPATH, xpath)

                    # Obtener valor según tipo de elemento
                    if element.tag_name == 'input':
                        valor = element.get_attribute('value') or ''
                    else:
                        valor = element.text.strip()

                    if valor:
                        resultados.append({
                            "code": code,
                            "value": valor,
                            "name": campo['name'],
                            "subject": campo['subject']
                        })
                        logger.debug(f"✅ {code}: {valor}")

                except Exception as e:
                    logger.debug(f"⚠️ Error extrayendo {code}: {str(e)}")
                    continue

            logger.info(f"🎯 Extraídos {len(resultados)} valores por XPath")
            return resultados

        except Exception as e:
            logger.error(f"❌ Error en extracción por XPath: {str(e)}")
            return []