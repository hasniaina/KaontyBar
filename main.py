from fastapi import FastAPI, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select, create_engine, SQLModel, delete
from models.models import Produit, TableBar, Consommation
from contextlib import asynccontextmanager


sqlite_url = "sqlite:///bar.db"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    # Initialisation rapide si vide
    with Session(engine) as session:
        if not session.exec(select(Produit)).first():
            session.add(Produit(nom="Bière", prix=2.5))
            session.add(Produit(nom="Café", prix=1.2))
            session.add(TableBar(numero=1))
            session.commit()
    yield

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

def get_session():
    with Session(engine) as session:
        yield session

@app.get("/")
async def home(request: Request, session: Session = Depends(get_session)):
    # On trie d'abord par 'est_payee' (False/0 d'abord), puis par 'numero'
    statement = select(TableBar).order_by(TableBar.est_payee, TableBar.numero)
    tables = session.exec(statement).all()
    
    produits = session.exec(select(Produit)).all()
    
    stats = {}
    for t in tables:
        total = sum(c.quantite * c.produit.prix for c in t.consommations)
        stats[t.id] = round(total, 2)

    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"tables": tables, "produits": produits, "stats": stats}
    )

@app.post("/ajouter-conso")
async def add_conso(table_id: int = Form(...), produit_id: int = Form(...),nombre:int = Form(...), session: Session = Depends(get_session)):
    # Vérifier si le produit est déjà sur l'ardoise de cette table
    statement = select(Consommation).where(Consommation.table_id == table_id, Consommation.produit_id == produit_id)
    conso = session.exec(statement).first()
    
    if conso:
        conso.quantite += nombre
        session.add(conso)
    else:
        nouvelle_conso = Consommation(table_id=table_id, produit_id=produit_id, quantite=nombre)
        session.add(nouvelle_conso)
        
    session.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/ajouter-table")
async def add_table(
    numero: int = Form(...), 
    session: Session = Depends(get_session)
):
    # Vérifier si le numéro de table existe déjà
    statement = select(TableBar).where(TableBar.numero == numero)
    existe = session.exec(statement).first()
    
    if not existe:
        nouvelle_table = TableBar(numero=numero)
        session.add(nouvelle_table)
        session.commit()
        
    return RedirectResponse(url="/", status_code=303)


@app.post("/payer/{table_id}")
async def payer_addition(table_id: int, session: Session = Depends(get_session)):
    table = session.get(TableBar, table_id)
    if table:
        # 1. Supprimer toutes les consommations liées à cette table
        # statement = delete(Consommation).where(Consommation.table_id == table_id)
        # session.exec(statement)
        
        # 2. Marquer la table comme payée (grisée)
        table.est_payee = True
        session.add(table)
        session.commit()
        
    return RedirectResponse(url="/", status_code=303)

@app.post("/ouvrir/{table_id}")
async def ouvrir_table(table_id: int, session: Session = Depends(get_session)):
    table = session.get(TableBar, table_id)
    if table:
        table.est_payee = False
        session.add(table)
        session.commit()
    return RedirectResponse(url="/", status_code=303)