"""
Script para corregir el encoding de los FAQs del SII
"""
import json
import html

def fix_encoding_in_text(text):
    """Corrige problemas comunes de encoding en texto"""
    if not text:
        return text

    # Decodificar entidades HTML
    text = html.unescape(text)

    # Reemplazos comunes de encoding incorrecto UTF-8
    replacements = {
        'Ã¡': 'á',
        'Ã©': 'é',
        'Ã­': 'í',
        'Ã³': 'ó',
        'Ãº': 'ú',
        'Ã±': 'ñ',
        'Ã‰': 'É',
        'Ã"': 'Ó',
        'Ãš': 'Ú',
        'Â¿': '¿',
        'Â¡': '¡',
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text

def fix_faq_encoding(faq):
    """Corrige el encoding de un FAQ individual"""
    return {
        'category': fix_encoding_in_text(faq.get('category', '')),
        'subtopic': fix_encoding_in_text(faq.get('subtopic', '')),
        'question': fix_encoding_in_text(faq.get('question', '')),
        'answer': fix_encoding_in_text(faq.get('answer', ''))
    }

def process_faqs_file(input_file='faqs_sii.json', output_file='faqs_sii_fixed.json'):
    """Procesa el archivo de FAQs y corrige el encoding"""

    # Leer archivo original
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Determinar estructura del archivo
    if isinstance(data, dict) and 'faqs' in data:
        # Estructura con metadata
        fixed_data = {
            'metadata': data.get('metadata', {}),
            'faqs': [fix_faq_encoding(faq) for faq in data['faqs']]
        }
    elif isinstance(data, list):
        # Lista directa de FAQs
        fixed_data = [fix_faq_encoding(faq) for faq in data]
    else:
        raise ValueError("Formato de archivo no reconocido")

    # Guardar archivo corregido
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(fixed_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Archivo corregido guardado en: {output_file}")

    # Mostrar ejemplos de correcciones
    if isinstance(fixed_data, dict) and 'faqs' in fixed_data:
        sample_faqs = fixed_data['faqs'][:3]
    else:
        sample_faqs = fixed_data[:3]

    print("\n📝 Ejemplos de FAQs corregidos:")
    for i, faq in enumerate(sample_faqs, 1):
        print(f"\n{i}. Categoría: {faq['category']}")
        print(f"   Pregunta: {faq['question'][:100]}...")

    return fixed_data

if __name__ == "__main__":
    import os
    os.chdir(os.path.dirname(__file__))
    process_faqs_file()