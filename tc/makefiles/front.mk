### FRONTEND
# ¯¯¯¯¯¯¯¯

front.ts: ## Create TS definitions from backend models
	pydantic2ts --module ./src/services/backend/models.py --output ./src/frontend/src/types/apiTypes.ts

front.build: ## Build React App for prod
	#yarn global add react-scripts-less
	#yarn add typescript@4.8.4
	yarn  --cwd ./src/frontend install
	yarn --cwd ./src/frontend build --profile

front.start: ## Start React App
	yarn  --cwd ./src/frontend start
