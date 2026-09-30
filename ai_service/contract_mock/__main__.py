"""Run the synthetic contract mock on loopback only."""
import uvicorn
from .server import create_mock_app

if __name__ == '__main__':
    uvicorn.run(create_mock_app(), host='127.0.0.1', port=8765, access_log=False)
