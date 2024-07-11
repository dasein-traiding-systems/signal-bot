SRC_DIR :=

.PHONY: help lint lint-fix image push run deploy undeploy clean test-api .EXPORT_ALL_VARIABLES
.DEFAULT_GOAL := help

help:  ## 💬 This help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

test: venv  ## 🎯 Unit tests for Flask app
	. .venv/bin/activate \
	&& pytest -v

rebuild:  ## Install venv
	python3 -m venv .venv
	. .venv/bin/activate
	pip install -Ur requirements.txt


