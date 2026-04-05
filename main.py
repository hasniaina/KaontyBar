from datetime import date, datetime

from fastapi import FastAPI, Request, Form, Depends, staticfiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sentry_sdk import session
from sqlmodel import Session, Table, desc, select, create_engine, SQLModel, delete
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
app.mount("/static", staticfiles.StaticFiles(directory="static"), name="static")
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

@app.post("/supprimer-conso")
async def remove_conso(table_id: int = Form(...), produit_id: int = Form(...), nombre: int = Form(...), session: Session = Depends(get_session)):
    # On récupère la table pour vérifier son statut
    table = session.get(TableBar, table_id)
    if not table or table.est_payee:
        return RedirectResponse(url="/", status_code=303)

    statement = select(Consommation).where(Consommation.table_id == table_id, Consommation.produit_id == produit_id)
    conso = session.exec(statement).first()
    
    if conso:
        if conso.quantite > nombre:
            conso.quantite -= nombre
            session.add(conso)
        else:
            session.delete(conso)
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
        # Marquer la table comme payée (grisée)
        table.est_payee = True
        table.date_payement = datetime.now().strftime("%Y-%m-%d, %H:%M:%S")# Enregistrer la date-heure du paiement
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


@app.get("/total-income/produits/")
async def total_income(request: Request, session: Session = Depends(get_session)):
# from sqlalchemy import desc

# On joint Consommation -> Table pour accéder à date_payement
    statement = (
        select(Consommation)
        .join(Consommation.table) # Utilise la relation définie dans ton modèle
        .where(Consommation.table.has(est_payee=True))
        .order_by(desc(Consommation.table.property.mapper.class_.date_payement))
    )

    consommations = session.exec(statement).all()
    
    total = sum(c.quantite * c.produit.prix for c in consommations)
    
    # On prépare les données pour le template
    details_list = [{
        "produit": c.produit.nom, 
        "quantite": c.quantite, 
        "prix_unitaire": c.produit.prix, 
        "total": round(c.quantite * c.produit.prix, 2)
    } for c in consommations]

    # IMPORTANT : Utiliser TemplateResponse pour envoyer du HTML
    # Ordre correct : request, "nom_du_template", {contexte}
    return templates.TemplateResponse(
        request,
        "income.html", 
        {
            "request": request, 
            "total_income": round(total, 2), 
            "details": details_list
        }
    )


@app.get("/stock")
async def get_stock_page(request: Request, session: Session = Depends(get_session)):
    produits = session.exec(select(Produit).order_by(Produit.nom)).all()
    return templates.TemplateResponse(request, "stock.html", {"request": request, "produits": produits})

@app.post("/stock/add")
async def add_stock(nom: str = Form(...), prix: float = Form(...), session: Session = Depends(get_session)):
    nouveau_produit = Produit(nom=nom, prix=prix)
    session.add(nouveau_produit)
    session.commit()
    return RedirectResponse(url="/stock", status_code=303)