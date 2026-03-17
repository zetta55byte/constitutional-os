import os
import sys
sys.path.insert(0, '/app/src')
import uvicorn
port = int(os.environ.get('PORT', 8000))
uvicorn.run('constitutional_os.console.api:app', host='0.0.0.0', port=port)
