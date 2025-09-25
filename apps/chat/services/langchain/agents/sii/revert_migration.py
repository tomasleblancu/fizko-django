"""
Script para revertir la migración al sistema optimizado
Generado automáticamente el 2025-09-24T22:50:50.759665
"""
import os
import shutil

def revert_migration():
    """Revierte los cambios de la migración"""
    base_dir = os.path.dirname(__file__)
    backup_dir = os.path.join(base_dir, 'backup_migration')

    if not os.path.exists(backup_dir):
        print("❌ No se encontraron archivos de backup")
        return

    print("🔙 Revirtiendo migración...")

    # Restaurar archivos desde backup
    backup_files = ['agent.py', 'tools.py', 'faq_retriever.py']

    for filename in backup_files:
        backup_path = os.path.join(backup_dir, f"{filename}.backup")
        if os.path.exists(backup_path):
            dest_path = os.path.join(base_dir, filename)
            shutil.copy2(backup_path, dest_path)
            print(f"   ✅ Restaurado: {filename}")

    # Restaurar __init__.py
    init_file = os.path.join(base_dir, '__init__.py')
    if os.path.exists(init_file):
        with open(init_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Revertir import
        content = content.replace(
            'from .optimized_agent import OptimizedSIIAgent as SIIAgent',
            'from .agent import SIIAgent'
        )

        with open(init_file, 'w', encoding='utf-8') as f:
            f.write(content)

        print("   ✅ __init__.py revertido")

    print("✅ Migración revertida exitosamente")

if __name__ == "__main__":
    revert_migration()
