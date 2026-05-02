# sharp-skies

Docs: http://127.0.0.1:8000/docs#/

1. Create a new env first
   1. python3 -m venv .venv
1. Activate the env in a new termina;
   source .venv/bin/activate

1. Run the app
   uvicorn app.main:app --reload

1. Create a requirements file for package sharing
   1. touch requirements.txt
   1. python -m pip freeze > requirements.txt
