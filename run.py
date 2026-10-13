#Student_ID_25017334_Name_Priyanshi_Jadeja

from app import create_app

app = create_app()
app.jinja_env.cache = {}   

print(">>> ALL REGISTERED ENDPOINTS:", list(app.view_functions.keys()))

if __name__ == "__main__":
    app.run(debug=True)