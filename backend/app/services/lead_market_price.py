"""Servicio de LeadMarketPrice (CC-014, Q-B; anulacion en el ciclo corto que sigue).

Append-only con anulacion: create + lecturas + `annul`, sin update y sin delete.
*Append-only significa que no se borra, no que no se pueda invalidar* — es el
criterio de `MoneyMovement`. La vigente es la de mayor `effective_date` ENTRE LAS
NO ANULADAS, con `created_at DESC, id DESC` como desempate; el desempate por id
es obligatorio porque `now()` de PG es transaccional y empata en cargas batch.

🔴 UN SOLO SELECTOR DEL VIGENTE, y es por DELEGACION (D3 del plan).
Antes del ciclo de anulacion habia tres `WHERE` escritos a mano — `get_all`,
`get_current` (que alimenta el balance por `reports.py`) y `get_current_response`
(que pinta "vigente" en Config) — y yo afirme en el plan que "el filtro vive en
un solo sitio" porque `_CURRENT_ORDER` era compartido. Era FALSO: lo compartido
era el ORDER BY. Con el filtro de anulados repartido a mano en dos copias, el
modo de falla es silencioso: **el balance usa el precio bueno y la pantalla
muestra como vigente el anulado**, o al reves, y todo test que mire UNA
superficie pasa en verde (#98: un argumento por construccion protege exactamente
la superficie sobre la que cuantifica).

Por eso `get_current` es el UNICO que decide que fila rige, y
`get_current_response` es `get_current` MAS el nombre del usuario, no una copia
del query. ⚠️ Si alguna vez se "optimiza" volviendo a escribir el select
completo aca, el test estrella lo caza: lee las dos superficies por HTTP en el
mismo escenario.

`get_all` queda SIN el filtro a proposito: el historico tiene que listar los
anulados, tachados y con su motivo, o la anulacion deja de ser auditable.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models.lead_market_price import LeadMarketPrice
from app.models.user import User
from app.schemas.lead_market_price import (
    LeadMarketPriceCreate,
    LeadMarketPriceResponse,
)

# Orden canonico de vigencia, en UN solo sitio: lo usan get_current y el
# historico. ⚠️ `annulled_at` NO entra aca (D6): la anulacion decide si una fila
# participa, no en que posicion queda.
_CURRENT_ORDER = (
    LeadMarketPrice.effective_date.desc(),
    LeadMarketPrice.created_at.desc(),
    LeadMarketPrice.id.desc(),
)


class LeadMarketPriceService:
    """Precio de mercado del plomo, append-only con vigencia por fecha de negocio."""

    def create(
        self,
        db: Session,
        obj_in: LeadMarketPriceCreate,
        organization_id: UUID,
        user_id: UUID,
    ) -> LeadMarketPrice:
        db_obj = LeadMarketPrice(
            organization_id=organization_id,
            price_per_kg=obj_in.price_per_kg,
            effective_date=obj_in.effective_date,
            notes=obj_in.notes,
            created_by=user_id,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def annul(
        self,
        db: Session,
        price_id: UUID,
        reason: str,
        organization_id: UUID,
        user_id: UUID,
    ) -> LeadMarketPriceResponse:
        """Anular un precio cargado por error. La fila NO se borra.

        ⚠️ Anular es otro back-dating: el precio deja de regir en TODOS los
        cortes, incluidos los ya impresos. Es coherente con #41 (lo anulado
        nunca existio) y esta cubierto por el costo que Daniel aprobo el 21-sep
        para la vigencia por fecha de negocio. El balance sigue imprimiendo
        `price_date`, asi que el corte queda auditable.
        """
        price = db.execute(
            select(LeadMarketPrice).where(
                LeadMarketPrice.id == price_id,
                LeadMarketPrice.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if price is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Precio de mercado no encontrado",
            )
        if price.annulled_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ese precio ya esta anulado.",
            )

        # Timestamp de AUDITORIA, no fecha de negocio (#91): responde *cuando
        # exactamente*, no *que dia*. Por eso `now(timezone.utc)` y no
        # `business_today()`, y por eso no participa del orden de vigencia.
        price.annulled_at = datetime.now(timezone.utc)
        price.annulled_by = user_id
        price.annulled_reason = reason
        db.commit()
        db.refresh(price)
        return self._response_with_names(db, price)

    def get_all(
        self,
        db: Session,
        organization_id: UUID,
    ) -> list[LeadMarketPriceResponse]:
        """Historico completo, el vigente primero. INCLUYE los anulados.

        Sin filtro a proposito: la pantalla los pinta tachados y con su motivo.
        Un historico que esconde lo anulado no sirve para auditar nada.
        ⚠️ Por eso "el primero de la lista" NO es el vigente — la pantalla tiene
        que preguntarselo a `/current` y comparar por id, nunca por indice.
        """
        annuller = aliased(User)
        query = (
            select(
                LeadMarketPrice,
                User.full_name.label("created_by_name"),
                annuller.full_name.label("annulled_by_name"),
            )
            .outerjoin(User, LeadMarketPrice.created_by == User.id)
            .outerjoin(annuller, LeadMarketPrice.annulled_by == annuller.id)
            .where(LeadMarketPrice.organization_id == organization_id)
            .order_by(*_CURRENT_ORDER)
        )
        return [self._to_response(row) for row in db.execute(query).all()]

    def get_current(
        self,
        db: Session,
        organization_id: UUID,
        cutoff_dt: Optional[datetime] = None,
    ) -> Optional[LeadMarketPrice]:
        """🔴 EL UNICO selector del vigente. Todo lo demas delega aca.

        `cutoff_dt` son las 00:00 del dia SIGUIENTE al corte (es lo que arma
        el balance) y se compara con `<`, igual que el resto de los saldos
        as-of. Como `effective_date` se guarda a mediodia UTC, un precio
        fechado el dia del corte entra.

        ⚠️ El filtro de anulados va FUERA del `if cutoff_dt`, y es a proposito:
        dentro de la rama solo protegeria uno de los dos caminos del balance
        (vivo y as-of) y el otro seguiria usando el precio anulado, con el test
        del camino vivo en verde. Hay un test que lee el balance as-of por eso.
        """
        query = (
            select(LeadMarketPrice)
            .where(
                LeadMarketPrice.organization_id == organization_id,
                LeadMarketPrice.annulled_at.is_(None),
            )
            .order_by(*_CURRENT_ORDER)
            .limit(1)
        )
        if cutoff_dt is not None:
            query = query.where(LeadMarketPrice.effective_date < cutoff_dt)
        return db.execute(query).scalars().first()

    def get_current_response(
        self,
        db: Session,
        organization_id: UUID,
    ) -> Optional[LeadMarketPriceResponse]:
        """El vigente con el nombre de quien lo cargo (para la pantalla).

        DELEGA en `get_current` — no repite el query. Es lo que garantiza que la
        pantalla y el balance no puedan discrepar sobre cual es el vigente.
        """
        price = self.get_current(db, organization_id)
        return self._response_with_names(db, price) if price else None

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #
    def _response_with_names(
        self, db: Session, price: LeadMarketPrice
    ) -> LeadMarketPriceResponse:
        """Response de UNA fila, resolviendo los dos nombres por separado.

        Dos `db.get` y no un JOIN: son lecturas por PK sobre el identity map,
        y el que delega (`get_current_response`) ya tiene la fila en la sesion.
        """
        resp = LeadMarketPriceResponse.model_validate(price)
        creator = db.get(User, price.created_by) if price.created_by else None
        resp.created_by_name = creator.full_name if creator else None
        annuller = db.get(User, price.annulled_by) if price.annulled_by else None
        resp.annulled_by_name = annuller.full_name if annuller else None
        return resp

    @staticmethod
    def _to_response(row) -> LeadMarketPriceResponse:
        price = row[0]
        resp = LeadMarketPriceResponse.model_validate(price)
        resp.created_by_name = row.created_by_name
        resp.annulled_by_name = row.annulled_by_name
        return resp


lead_market_price = LeadMarketPriceService()
