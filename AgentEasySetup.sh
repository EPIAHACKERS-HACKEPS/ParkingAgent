#!/bin/bash

# Hacer el script ejecutable: chmod +x AgentEasySetup.sh

echo "=== Agent Easy Setup ==="

# Crear y activar entorno virtual
echo "Creando entorno virtual..."
python3 -m venv venv || { echo "Error: No se pudo crear el entorno virtual."; exit 1; }
echo "Activando entorno virtual..."
source venv/bin/activate || { echo "Error: No se pudo activar el entorno virtual."; exit 1; }

# Instalar dependencias
echo "Instalando dependencias..."
pip install -r requirements.txt || { echo "Error: No se pudieron instalar las dependencias."; exit 1; }

# Ejecutar el script principal
echo "Iniciando el script parking.py..."
python parking.py &

echo "Setup completado. parking.py está ejecutándose en segundo plano."
