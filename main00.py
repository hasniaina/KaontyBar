from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI() # declaration de l'application

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get('/hasiniaina/{item1}/{item2}')
def read_item(item1:int, item2:int, query:str=None):
    return {"item1_id": item1, "item2_id": item2, "params_query": query}


# Définition du format de donnée attendu
class Item(BaseModel):
    nom:str
    prenom:str
    age:int

@app.put('/testapi/{itemID}')
def update_item(itemID:int, item:Item):
    return { "item ID": itemID, "nom et prenom": item.nom + " " + item.prenom, "age": item.age }