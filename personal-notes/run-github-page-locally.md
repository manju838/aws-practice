# How to run Github Page locally?

1. Start Docker Desktop
2. Check if docker is accessed from terminal using ```docker ps```
3. Run ```tools/serve.sh``` inside the terminal. ```serve.sh``` starts docker and builds your environment inside a docker container.
```bash
docker ps
tools/serve.sh
```