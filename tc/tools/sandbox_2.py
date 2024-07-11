from pydantic2ts import generate_typescript_defs

generate_typescript_defs("services/backend/models.py", "./frontend/src/types/apiTypes.ts", json2ts_cmd="yarn json2ts")