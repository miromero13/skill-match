# Plan de Implementación — SM-54 (HU-42)
## Billetera de Puntos: Recarga, pago de clases y retiro de dinero (Cashout)

---

### 1. Resumen Ejecutivo y Trazabilidad

| Atributo | Detalle |
| :--- | :--- |
| **ID Historia Jira** | [SM-54](https://sauterdevs.atlassian.net/browse/SM-54) (HU-42) |
| **Épica** | SM-12: EPIC-12: Economía de Puntos, Billetera y Resolución de Quejas |
| **Prioridad** | Highest (Sprint 4) |
| **Responsable** | Bernardo Chavez Padilla |
| **Rama Git de Trabajo** | `feat/hu-42-wallet-points` (creada a partir de `dev` actualizado con PR #15 y últimos cambios) |
| **Criterios de Aceptación** | **RF-SES-09**, **RF-WAL-01**, **RF-WAL-02** |
| **Prototipos de Referencia** | **Web Desktop:** `13A - Billetera de Tokens & Balance Escrow`, `13B - Modal Adquisición` y `13C - Modal Canje y Retiro`<br>**Mobile Responsive:** `15A - Mobile Billetera`, `15B - Modal Adquisición` y `15C - Modal Canje y Retiro` |

---

### 2. Alcance Visual & Funcional (OpenPencil Exact Alignment)

1. **Dashboard de Billetera (Vistas 13A Desktop / 15A Mobile)**:
   - Header con saldo destacado de tokens (`SP` - SkillPoints) y equivalente monetario en USD (tasa estándar: 10 SP = $1.00 USD).
   - Cuadrícula de 4 tarjetas de balance:
     - **Saldo Disponible**: Puntos libres listos para intercambios o reservas directas.
     - **Retenido en Escrow**: Puntos en custodia temporal asociados a sesiones agendadas o en curso.
     - **Propinas & Recompensas**: Puntos acumulados por excelencia pedagógica y mentorías evaluadas con 5 estrellas, 100% elegibles para Cashout.
     - **Tarifa de Servicio de Plataforma**: Indicador informativo de la comisión institucional por retiro a cuenta bancaria (15%).
   - Botones de acción principales:
     - Botón `Adquirir SkillPoints` / `Recargar`: Abre el modal 13B / 15B.
     - Botón `Canjear Recompensas (Cashout)` / `Retirar Fondos`: Abre el modal 13C / 15C.
   - Historial de Transacciones Contables:
     - Auditoría de movimientos con filtros por pestañas: `Todas`, `Recargas (TOPUP)`, `Clases (CLASS_PAYMENT)`, `Propinas (TIP)`, `Retiros (CASHOUT)`, `Recompensas (ADMIN_REWARD)`.
     - Datos por fila: Descripción de la operación, contraparte o sesión asociada, fecha/hora formateada, identificador/hash contable (`tx:0x...`) y monto formateado (`+` verde esmeralda para créditos, `-` ámbar/rojo para débitos).

2. **Modal de Adquisición de SkillPoints (Vistas 13B Desktop / 15B Mobile)**:
   - Título: `Adquirir Paquete de SkillPoints`.
   - Selector visual de 4 paquetes de puntos:
     - **Paquete Básico**: 100 SP · Sin bonus · **$10 USD**
     - **Paquete Estudiante (MÁS POPULAR)**: 250 SP · +25 SP Bonus (10%) · **$25 USD**
     - **Paquete Pro**: 500 SP · +75 SP Bonus (15%) · **$50 USD**
     - **Paquete Master**: 1000 SP · +200 SP Bonus (20%) · **$100 USD**
   - Formulario de pasarela de pagos simulada:
     - Método de pago (Tarjeta Visa / Mastercard terminada en `•••• 4291` o ingreso de datos seguros).
   - Botón CTA: `Confirmar Pago ($XX USD) & Acreditar XXX SP` con animación de carga y confirmación inmediata en la billetera.

3. **Modal de Canje y Retiro de Recompensas (Cashout) (Vistas 13C Desktop / 15C Mobile)**:
   - Título: `Canjear Recompensas Pedagógicas (Cashout)`.
   - Subtítulo explicativo: *"Convertí tus puntos obtenidos por mentorías de 5 estrellas y propinas en dinero real a tu cuenta bancaria."*
   - Saldo canjeable disponible (solo puntos generados por enseñanza y propinas).
   - Selector/input numérico de puntos a retirar (con validación de mínimo de retiro, ej. 100 SP = $10 USD).
   - **Cálculo Reactivo en Tiempo Real**:
     - Monto Bruto en USD: `points / 10`.
     - Comisión de Servicio de Plataforma (15%): `gross * 0.15`.
     - Monto Neto a Transferir: `gross - commission`.
   - Formulario de datos bancarios para transferencia:
     - Entidad bancaria / Institución financiera.
     - Tipo de cuenta (Corriente / Ahorros en USD) y Número de cuenta.
     - Nombre completo del titular y Documento de Identidad (CI / DNI / Tax ID).
   - Aviso de seguridad: *"Las transferencias son validadas en 24h tras comprobar que las sesiones asociadas no tengan disputas pendientes."*
   - Botón CTA: `Solicitar Retiro de Fondos ($XX.XX USD)` con confirmación modal y toast descriptivo.

---

### 3. Arquitectura de Backend (FastAPI + SQLAlchemy 2.0 + Alembic)

#### 3.1 Modelos de Datos (`backend/app/models/wallet.py`)
1. **Actualización de `Wallet`**:
   - `user_id: UUID` (PK, FK `users.id`)
   - `balance: int` (Constraint `balance >= 0`, puntos disponibles)
   - `escrow_balance: int` (Constraint `escrow_balance >= 0`, puntos retenidos en garantía)
   - `created_at`, `updated_at`

2. **Nuevo Modelo `PointTransaction` (`point_transactions`)**:
   - `id: UUID` (PK, default uuid4)
   - `user_id: UUID` (FK `users.id`, indexado)
   - `amount: int` (Valor con signo: positivo ingreso, negativo egreso)
   - `balance_after: int` (Saldo resultante disponible)
   - `escrow_after: int` (Saldo resultante en custodia)
   - `transaction_type: str` (Enum/String: `TOPUP`, `CLASS_PAYMENT`, `TIP`, `CASHOUT`, `ADMIN_REWARD`)
   - `reference_id: UUID | None` (ID de sesión, cashout_request o pago)
   - `description: str` (Detalle descriptivo de la transacción)
   - `created_at: datetime`

3. **Nuevo Modelo `CashoutRequest` (`cashout_requests`)**:
   - `id: UUID` (PK, default uuid4)
   - `user_id: UUID` (FK `users.id`, indexado)
   - `points_amount: int` (Constraint `>= 100`, mínimo de retiro)
   - `gross_amount_usd: Numeric(10, 2)`
   - `fee_percentage: Numeric(5, 2)` (15.00)
   - `fee_amount_usd: Numeric(10, 2)`
   - `net_amount_usd: Numeric(10, 2)`
   - `status: str` (Constraint: `status IN ('PENDING', 'APPROVED', 'REJECTED')`, default `PENDING`)
   - `bank_name: str`
   - `account_number: str`
   - `account_holder_name: str`
   - `account_holder_id: str`
   - `admin_notes: str | None`
   - `reviewed_at: datetime | None`
   - `created_at: datetime`

#### 3.2 Migración Alembic
- Generar script de migración versionado en `backend/alembic/versions/` para:
  - Alterar tabla `wallets` agregando columna `escrow_balance` con valor default 0 y constraint `ck_wallet_nonnegative_escrow`.
  - Crear tabla `point_transactions` con índices y constraints.
  - Crear tabla `cashout_requests` con constraints de estado y montos.

#### 3.3 Esquemas Pydantic (`backend/app/schemas/wallet.py`)
- `WalletBalanceResponse`: `balance`, `escrow_balance`, `rewards_balance`, `total_balance`, `usd_equivalent`, `exchange_rate` (10 SP = $1 USD).
- `TopupPackage`: `package_id`, `name`, `points`, `bonus_points`, `total_points`, `price_usd`, `is_popular`.
- `TopupRequest`: `package_id: str`, `payment_method: str`, `card_last_four: str | None`.
- `TopupResponse`: `transaction_id`, `points_added`, `new_balance`, `message`.
- `CashoutRequestCreate`: `points_amount: int` (ge=100), `bank_name: str`, `account_number: str`, `account_holder_name: str`, `account_holder_id: str`.
- `CashoutCalculationResponse`: `points_amount`, `gross_amount_usd`, `fee_percentage`, `fee_amount_usd`, `net_amount_usd`.
- `CashoutRequestResponse`: Datos completos de la solicitud registrada.
- `PointTransactionItem`: Datos serializados de una transacción contable.
- `PointTransactionListResponse`: Lista paginada con total y `count`.

#### 3.4 Lógica de Negocio y Servicios (`backend/app/services/wallet_service.py`)
- `get_or_create_wallet(db, user_id)`: Asegura la existencia de la billetera del miembro.
- `get_balance(db, user)`: Calcula balance disponible, escrow y puntos provenientes de propinas/clases.
- `topup(db, user, payload)`: Acredita puntos y bonus según el paquete, registra transacción `TOPUP`.
- `create_cashout_request(db, user, payload)`: Valida saldo disponible >= `points_amount`, mínimo 100 SP, deduce balance disponible, registra transacción `CASHOUT` (egreso) y crea `CashoutRequest` en `PENDING`.
- `list_transactions(db, user, type_filter, page, page_size)`: Paginación y filtrado de transacciones.
- **Flujo de Escrow en Sesiones (`POST /api/sessions/{id}/pay`)**:
  - `lock_session_escrow(db, session_id, learner_id, points)`: Descuenta `balance`, aumenta `escrow_balance`, actualiza sesión `payment_state = 'RESERVED'`.
  - `release_session_escrow(db, session_id)`: Al confirmarse la sesión (`COMPLETED`), descuenta `escrow_balance` del alumno y acredita `balance` al instructor como `CLASS_PAYMENT`, actualizando sesión `payment_state = 'RELEASED'`.
  - `refund_session_escrow(db, session_id)`: Si la sesión es cancelada o anulada, regresa `escrow_balance` a `balance` del alumno con estado `REFUNDED`.

#### 3.5 Endpoints REST (`backend/app/api/wallet/router.py`)
- `GET /api/wallet/balance`: Consulta saldo y equivalente monetario.
- `POST /api/wallet/topup`: Recarga de puntos con selección de paquete.
- `POST /api/wallet/cashout`: Envío de solicitud de retiro bancario.
- `POST /api/wallet/cashout/calculate`: Endpoint auxiliar para cálculo en tiempo real de comisión y neto.
- `GET /api/wallet/transactions`: Historial paginado con filtro opcional de tipo.
- `POST /api/sessions/{session_id}/pay`: Pagar / asegurar sesión con puntos y retención Escrow.

---

### 4. Arquitectura de Frontend (React 19 + TypeScript + Zustand + Tailwind + Shadcn Mist)

#### 4.1 Tipado & Contratos (`frontend/src/types/wallet.ts`)
- Tipos de datos para balances, paquetes, transacciones contables, solicitudes de cashout y filtros.

#### 4.2 Servicio API (`frontend/src/services/wallet-service.ts`)
- Métodos tipados consumiendo el cliente Axios centralizado (`@/lib/api-client`):
  - `getWalletBalance()`
  - `topupWallet(payload)`
  - `requestCashout(payload)`
  - `calculateCashout(points)`
  - `getTransactions(params)`
  - `paySession(sessionId)`

#### 4.3 Store Zustand (`frontend/src/stores/wallet-store.ts`)
- Estado global de billetera:
  - `balance`, `escrowBalance`, `rewardsBalance`, `usdEquivalent`, `packages`.
  - `transactions`, `totalTransactions`, `page`, `pageSize`, `filterType`.
  - Modales: `isTopupModalOpen`, `isCashoutModalOpen`.
  - Acciones: `fetchBalance`, `fetchTransactions`, `topup`, `cashout`, `setFilterType`, `openTopupModal`, `openCashoutModal`, etc.

#### 4.4 Componentes de Interfaz de Usuario
- [wallet-page.tsx](file:///home/chavezin/Desktop/skill-match/frontend/src/pages/wallet/wallet-page.tsx): Vista integral de billetera con métricas de balance, botones de acción y tabla contable.
- [topup-modal.tsx](file:///home/chavezin/Desktop/skill-match/frontend/src/components/wallet/topup-modal.tsx): Modal de adquisición de paquetes (13B / 15B) con badges de popularidad, cálculo de bonus y confirmación de pago.
- [cashout-modal.tsx](file:///home/chavezin/Desktop/skill-match/frontend/src/components/wallet/cashout-modal.tsx): Modal de canje (13C / 15C) con slider/input de puntos, cálculo interactivo de comisión (15%) y datos bancarios.
- [transaction-history-table.tsx](file:///home/chavezin/Desktop/skill-match/frontend/src/components/wallet/transaction-history-table.tsx): Tabla accesible y responsive con badges de color por tipo de transacción y hash de auditoría.
- **Actualización de Navegación**:
  - Sidebar ([app-sidebar.tsx](file:///home/chavezin/Desktop/skill-match/frontend/src/components/layout/app-sidebar.tsx)): Agregar enlace "Mi Billetera" con badge visible del saldo actual en puntos para miembros.
  - Header ([platform-header.tsx](file:///home/chavezin/Desktop/skill-match/frontend/src/components/layout/platform-header.tsx)): Sincronización del badge de puntos con el store de Zustand.
- **Rutas**:
  - Registrar `/wallet` y `/app/wallet` protegidas para miembros en [routes/index.tsx](file:///home/chavezin/Desktop/skill-match/frontend/src/routes/index.tsx).

---

### 5. Plan de Pruebas Automatizadas

1. **Backend (Pytest)**:
   - `test_wallet_balance_initialization`: Saldo inicial y equivalente monetario en USD.
   - `test_wallet_topup_packages`: Acreditación de puntos y bonus por paquete con registro en `point_transactions`.
   - `test_wallet_cashout_validation_and_fee`: Validación de mínimo 100 SP, cálculo de comisión 15%, deducción de balance y creación de `CashoutRequest`.
   - `test_wallet_cashout_insufficient_funds`: Rechazo con error descriptivo si el usuario no tiene saldo suficiente.
   - `test_session_escrow_lifecycle`: Retención de puntos al pagar sesión no recíproca (`RESERVED`) y liberación automática al tutor al completarse (`RELEASED`).
   - `test_wallet_transactions_pagination_and_filtering`: Filtro por tipo (`TOPUP`, `CASHOUT`, etc.) y paginación con `count`.

2. **Frontend (Vitest + Testing Library)**:
   - Renderizado correcto del balance disponible y retenido en escrow.
   - Interacción con el modal de recarga y selección de paquetes.
   - Cálculo reactivo en el modal de cashout (comisión 15% y monto neto en USD).
   - Filtrado de transacciones por tipo.
   - Validación de campos bancarios obligatorios en el formulario de retiro.
   - Toasts mostrando el `message` exacto del backend.

---

### 6. Criterio de "Done" y Entregables
1. Todas las pruebas de backend y frontend pasando al 100%.
2. Compilación de Vite en modo producción sin errores TypeScript (`npm run build`).
3. Commit bajo *Conventional Commits* en inglés (`feat(wallet): ... closes SM-54`).
4. Push a origin de la rama `feat/hu-42-wallet-points`.
5. Pull Request creado hacia la rama `dev` con detalle de criterios cumplidos.
6. Actualización del ticket Jira SM-54 a estado **"En revisión"** con enlace al PR.
