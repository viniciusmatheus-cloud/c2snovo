# Entry point para o Railway
import importlib.util, sys, os

spec = importlib.util.spec_from_file_location("app", os.path.join(os.path.dirname(__file__), "iniciar.py"))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
app.main()
