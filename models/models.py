from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional

class Produit(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str
    prix: float
    consommations: List["Consommation"] = Relationship(back_populates="produit")

class TableBar(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    numero: int
    est_payee: bool = Field(default=False) # Nouveau champ
    consommations: List["Consommation"] = Relationship(back_populates="table")
    date_payement: Optional[str] = Field(default=None) # Nouveau champ

class Consommation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    quantite: int = Field(default=1)
    
    table_id: int = Field(foreign_key="tablebar.id")
    produit_id: int = Field(foreign_key="produit.id")
    
    table: TableBar = Relationship(back_populates="consommations")
    produit: Produit = Relationship(back_populates="consommations")