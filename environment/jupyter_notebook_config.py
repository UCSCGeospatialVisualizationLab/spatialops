# Disable authentication
c.NotebookApp.token = ""
# This equates to the password "access" to access the Jupyter instance
# c.NotebookApp.password = "argon2:$argon2id$v=19$m=10240,t=10,p=8$uk7hN5aqi1YAyECHjcNYtQ$qoMI+R5xTpkDZWrjiB3dDI/mL0rByN/zQvqsjcCQ/VM"
c.NotebookApp.password = ""
# Explicitly disable authentication
c.NotebookApp.password_required = False
c.NotebookApp.open_browser = True
c.NotebookApp.ip = "0.0.0.0"
c.NotebookApp.allow_root = True
c.NotebookApp.allow_remote_access = True
c.NotebookApp.allow_origin = "*"
c.NotebookApp.trust_xheaders = True
# c.NotebookApp.default_url = "lab"
c.NotebookApp.base_url = ""
