### FORMAT
# ¯¯¯¯¯¯¯¯

format.black: ## Run black on every file
	black src/ --config .flake8


format.isort: ## Sort imports
	isort -rc src/
