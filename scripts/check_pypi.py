import urllib.request
import json

packages = ['langchain', 'openai', 'vllm']
for pkg in packages:
    try:
        data = json.loads(urllib.request.urlopen(f'https://pypi.org/pypi/{pkg}/json').read())
        info = data.get('info', {})
        print(f"{pkg}:")
        print(f"  maintainer_email: {repr(info.get('maintainer_email', 'EMPTY'))}")
        print(f"  author_email: {repr(info.get('author_email', 'EMPTY'))}")
    except Exception as e:
        print(f"{pkg}: Error {e}")
