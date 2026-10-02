# How to run Github Page locally?

1. Start Docker Desktop
2. Check if docker is accessed from terminal using ```docker ps```
3. Run ```tools/serve.sh``` inside the terminal. ```serve.sh``` starts docker and builds your environment inside a docker container.
```bash
docker ps
tools/serve.sh
```
4. The content will be available at ```http://localhost:4000/aws-practice/``` in your browser and auto reloads after every save.