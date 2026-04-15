FROM node:20-alpine

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

EXPOSE 5173

# Exponemos hacia la red de docker para que podamos acceder por localhost
CMD ["npm", "run", "dev", "--", "--host"]
