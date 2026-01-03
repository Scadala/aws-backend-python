.PHONY: build-HelloWorldFunction

build-HelloWorldFunction:
	pip install uv
	uv pip compile pyproject.toml -o requirements.txt
	uv pip install --system -r requirements.txt --target "$(ARTIFACTS_DIR)"
	rm requirements.txt
	cp -r __init__.py app.py templates "$(ARTIFACTS_DIR)"
