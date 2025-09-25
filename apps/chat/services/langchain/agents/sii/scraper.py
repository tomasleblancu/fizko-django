import requests
from bs4 import BeautifulSoup
import time
from typing import Dict, List, Optional
import logging
import json
import os
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SIIFAQScraper:
    BASE_URL = "https://www.sii.cl/preguntas_frecuentes/"
    INITIAL_URL = f"{BASE_URL}otros.html"
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # segundos
    
    def __init__(self):
        self.session = requests.Session()
        self.faqs = []
        self.stats = {
            'total_categories': 0,
            'total_subtopics': 0,
            'total_questions': 0,
            'total_answers': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
        
    def get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """Obtiene el contenido HTML de una URL con reintentos."""
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return BeautifulSoup(response.text, 'html.parser')
            except requests.RequestException as e:
                logger.error(f"Error al obtener la página {url} (intento {attempt + 1}/{self.MAX_RETRIES}): {str(e)}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
                else:
                    self.stats['errors'] += 1
                    return None
                    
    def extract_onclick_url(self, div) -> Optional[str]:
        """Extrae la URL del atributo onclick de un div."""
        try:
            onclick = div.get('onclick', '')
            if 'window.location=' in onclick:
                return onclick.split("'")[1]
            return None
        except Exception as e:
            logger.error(f"Error al extraer URL onclick: {str(e)}")
            return None
        
    def process_main_page(self) -> List[Dict]:
        """Procesa la página principal de FAQs."""
        soup = self.get_soup(self.INITIAL_URL)
        if not soup:
            return []
            
        faq_items = []
        for div in soup.find_all('div', class_='caja-item'):
            try:
                onclick_url = self.extract_onclick_url(div)
                if onclick_url:
                    title = div.find('span', class_='titulo-item').text.strip()
                    full_url = f"{self.BASE_URL}{onclick_url}"
                    faq_items.append({
                        'title': title,
                        'url': full_url
                    })
            except Exception as e:
                logger.error(f"Error al procesar item de categoría: {str(e)}")
                self.stats['errors'] += 1
                
        self.stats['total_categories'] = len(faq_items)
        return faq_items
        
    def process_subtopics(self, url: str) -> List[Dict]:
        """Procesa los subtemas de una categoría."""
        soup = self.get_soup(url)
        base_url = '/'.join(url.split('/')[:-1])
        if not soup:
            return []
            
        subtopics = []
        listado = soup.find('div', id='listado_subtemas')
        if listado:
            for li in listado.find_all('li'):
                try:
                    link = li.find('a')
                    if link:
                        subtopics.append({
                            'title': link.text.strip(),
                            'url': f"{base_url}/{link['href']}"
                        })
                except Exception as e:
                    logger.error(f"Error al procesar subtema: {str(e)}")
                    self.stats['errors'] += 1
                    
        self.stats['total_subtopics'] += len(subtopics)
        return subtopics
        
    def process_questions(self, url: str) -> List[Dict]:
        """Procesa las preguntas de un subtema."""
        soup = self.get_soup(url)
        base_url = '/'.join(url.split('/')[:-1])
        if not soup:
            return []
            
        questions = []
        listado = soup.find('div', id='listado-preguntas-por-tema')
        if listado:
            for li in listado.find_all('li'):
                try:
                    link = li.find('a')
                    if link:
                        questions.append({
                            'question': link.text.strip(),
                            'url': f"{base_url}/{link['href']}"
                        })
                except Exception as e:
                    logger.error(f"Error al procesar pregunta: {str(e)}")
                    self.stats['errors'] += 1
                    
        self.stats['total_questions'] += len(questions)
        return questions
        
    def get_answer(self, url: str) -> Optional[str]:
        """Obtiene la respuesta de una pregunta."""
        soup = self.get_soup(url)
        if not soup:
            return None
            
        try:
            respuesta_div = soup.find('div', id='div-respuesta')
            if respuesta_div:
                answer = respuesta_div.get_text(strip=True)
                self.stats['total_answers'] += 1
                return answer
            return None
        except Exception as e:
            logger.error(f"Error al obtener respuesta: {str(e)}")
            self.stats['errors'] += 1
            return None
        
    def validate_faq(self, faq: Dict) -> bool:
        """Valida que una FAQ tenga todos los campos requeridos."""
        required_fields = ['category', 'subtopic', 'question', 'answer']
        return all(field in faq and faq[field] for field in required_fields)
        
    def save_to_json(self, data: List[Dict], filename: str = "faqs_sii.json"):
        """Guarda los resultados en un archivo JSON con metadatos."""
        filepath = os.path.join(os.path.dirname(__file__), filename)
        try:
            output = {
                'metadata': {
                    'total_faqs': len(data),
                    'scrape_date': datetime.now().isoformat(),
                    'stats': self.stats
                },
                'faqs': data
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
            logger.info(f"Resultados guardados exitosamente en {filepath}")
        except Exception as e:
            logger.error(f"Error al guardar el archivo JSON: {str(e)}")
        
    def scrape_all(self):
        """Ejecuta el proceso completo de scraping."""
        self.stats['start_time'] = datetime.now()
        logger.info("Iniciando proceso de scraping de FAQs del SII")
        
        main_items = self.process_main_page()
        
        for item in main_items:
            logger.info(f"Procesando categoría: {item['title']}")
            subtopics = self.process_subtopics(item['url'])
            
            for subtopic in subtopics:
                logger.info(f"Procesando subtema: {subtopic['title']}")
                questions = self.process_questions(subtopic['url'])
                
                for question in questions:
                    logger.info(f"Procesando pregunta: {question['question']}")
                    answer = self.get_answer(question['url'])
                    
                    if answer:
                        faq = {
                            'category': item['title'],
                            'subtopic': subtopic['title'],
                            'question': question['question'],
                            'answer': answer
                        }
                        
                        if self.validate_faq(faq):
                            self.faqs.append(faq)
                        else:
                            logger.warning(f"FAQ inválida encontrada: {faq}")
                            self.stats['errors'] += 1
                    
        self.stats['end_time'] = datetime.now()
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        logger.info(f"Proceso de scraping completado en {duration:.2f} segundos")
        logger.info(f"Estadísticas: {self.stats}")
        
        return self.faqs

def main():
    scraper = SIIFAQScraper()
    faqs = scraper.scrape_all()
    
    # Guardar los resultados en un archivo JSON
    scraper.save_to_json(faqs)
    print(f"Se encontraron {len(faqs)} FAQs")

if __name__ == "__main__":
    main()
