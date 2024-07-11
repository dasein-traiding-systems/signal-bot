### DEV/INIT
# ¯¯¯¯¯¯¯¯

server.init: ## Initialize directory structure and create docker images
	sh ./makefiles/init.sh

dev.init:  ## Install dependencies
	npm install -g json-schema-to-typescript --save

dev.venv: ## Activate venv
	source ./venv/bin/activate

dev.pip: ## Update requirements
	pip install -r requirements-dev.txt