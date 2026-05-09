import sys
import os

# Garantiza que la raíz del proyecto esté en sys.path cuando pytest
# se ejecuta desde cualquier directorio.
sys.path.insert(0, os.path.dirname(__file__))
