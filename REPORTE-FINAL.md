# Reporte final — Reestructuración Azure DevOps "Algoritmia IA"

Fecha: 2026-05-16
Organización: https://algoritmia8.visualstudio.com
Proyecto: `Algoritmia IA` (CMMI — proceso `Metodología Algoritmia`)
Equipo: `Grupo IA`

---

## 1. Resumen ejecutivo

Se ha reorganizado el proyecto ADO para reflejar el plan de negocio del Grupo de IA, con jerarquía CMMI **Epic → Feature → Requirement → Task**, Area Paths por PO, iteraciones bisemanales hasta cierre de 2026, KPIs mensuales trazables y un dashboard ejecutivo de seguimiento.

| Elemento | Cantidad |
|---|---|
| Epics | 7 |
| Features | 29 (IDs #13829–#13862, con huecos) |
| Requirements (backlog) | 37 (#13863–#13899) |
| Tasks de arranque | 59 (#13900–#13958) |
| KPI Requirements mensuales | 98 (#13959–#14056) |
| Queries compartidas | 6 |
| Dashboard widgets | 6 |

---

## 2. Estructura organizativa

### 2.1 Area Paths (8)
- `Algoritmia IA\Coordinación`
- `Algoritmia IA\Customer Engagement`
- `Algoritmia IA\Business Central`
- `Algoritmia IA\Finance`
- `Algoritmia IA\SCM`
- `Algoritmia IA\Prog. Finance-PP`
- `Algoritmia IA\Prog. Web-Data`
- `Algoritmia IA\Azure`

### 2.2 POs / Owners
| Área | PO | En ADO |
|---|---|---|
| Coordinación | Iván Font (`ifont@algoritmia8.com`) | sí |
| Customer Engagement | Miriam Artero | sí |
| Business Central | Laura Florido | sí |
| Finance | Omar Folqués | sí |
| SCM | Dani Gaya | **NO** (items etiquetados `po-pendiente`) |
| Prog. Finance-PP | Adrián Salas | sí |
| Prog. Web-Data | Paula Romero | sí |
| Azure | Carles Gelonch | sí |

### 2.3 Iterations (sprints de 2 semanas)
- `2026\Q2\Sprint-01` (18 May → 31 May) — activo
- `2026\Q2\Sprint-02..03`
- `2026\Q3\Sprint-04..10`
- `2026\Q4\Sprint-11..15`

---

## 3. Epics (7)

Todas en `Algoritmia IA\Coordinación`, owner Iván Font.

1. 🚀 Arranque y Gobierno *(reaprovecha #13816)*
2. 📡 Vigilancia Tecnológica
3. 📚 Base de Conocimiento
4. 🎓 Formación Interna
5. 🧪 Laboratorio de Innovación
6. 💼 Portfolio de Soluciones
7. 🤝 Soporte al Equipo

> Epics legacy #13817–#13820 cerradas como `Removed`.

---

## 4. KPIs mensuales

98 Requirements de tipo KPI (#13959–#14056), distribuidos como:
- 7 áreas × 7 meses (Jun–Dic 2026) × 2 KPIs (radar + knowledge) = **98**
- Estado inicial: `00 - Identificado`
- Tag: `kpi-mensual`
- **Asignación**: deliberadamente **sin asignar** (regla permanente). Los POs los toman al iniciar el mes.

---

## 5. Queries compartidas

Ruta: `Shared Queries\Grupo IA`

| Query | ID |
|---|---|
| KPI Radar — pendientes | `91ee2854-260f-40ba-8665-3d64ed4cf030` |
| KPI Knowledge — pendientes | `3d0efcc1-20ea-4233-96d7-9cc8d2bcd62b` |
| Backlog por Área | `fceb007d-4d3f-4497-92b2-95bc1a92bf71` |
| Roadmap por Iteración | `737b26fe-e451-4ea0-96a3-1f6c564bcd6e` |
| Sprint-01 — Tareas | `196cf828-3e35-4eb5-84c5-50ee5dc522cc` |
| Items sin asignar | `da523e31-0e36-43e1-9533-3e188390c7d8` |

---

## 6. Dashboard

**Nombre**: `Grupo IA - Seguimiento`
**ID**: `2497d01d-3104-4879-8cb4-facc0b4cc95b`
**URL**: https://algoritmia8.visualstudio.com/Algoritmia%20IA/_dashboards/dashboard/2497d01d-3104-4879-8cb4-facc0b4cc95b

Widgets (6 tiles scalar):

| Posición | Widget | Query |
|---|---|---|
| 1,1 | KPI Radar pendientes | KPI Radar — pendientes |
| 1,2 | KPI Knowledge pendientes | KPI Knowledge — pendientes |
| 1,3 | Items sin asignar | Items sin asignar |
| 1,4 | Sprint-01 — Tareas (n) | Sprint-01 — Tareas |
| 2,1 | Backlog por Área | Backlog por Área |
| 2,2 | Roadmap por Iteración | Roadmap por Iteración |

> Nota: se intentó usar `QueryResultsWidget` para las dos celdas inferiores, pero la API del proceso CMMI custom devuelve `VS402507: No widget of this type could be found` para ese contributionId. Se sustituyó por `QueryScalarWidget` (contador) para garantizar despliegue.

---

## 7. Verificación

- [x] 8 Area Paths creados.
- [x] 15 sprints creados con fechas.
- [x] Default iteration del equipo = `Sprint-01`.
- [x] 7 Epics activas + epics legacy removidas.
- [x] 29 Features ligadas a Epics.
- [x] 37 Requirements ligados a Features (backlog).
- [x] 59 Tasks ligadas a Requirements (Sprint-01).
- [x] 98 KPI Requirements mensuales (Jun–Dic 2026), sin asignar, tag `kpi-mensual`.
- [x] 6 queries compartidas funcionando.
- [x] Dashboard con 6 widgets desplegado y accesible.

---

## 8. Pendientes / próximos pasos

1. **Onboarding Dani Gaya** en ADO → reasignar los 14 items con tag `po-pendiente` (área SCM).
2. **Kickoff Sprint-01** (18 May): que cada PO coja sus 2 KPIs de Junio.
3. **Refinamiento de tags** opcional: añadir `arranque`, `Q3`, `Q4` para cortes adicionales en el dashboard.
4. **Confirmación funcional** con Iván y Ricard antes de comunicar al resto del equipo.

---

## 9. Artefactos en el repo

- `scripts/epics.json`, `features.json`, `requirements.json`, `tasks.json`, `kpis.json` — datos fuente.
- `scripts/01-areas.ps1` … `09-dashboard.ps1` — scripts idempotentes de creación.
- `plan-negocio-ia.html`, `presentacion-grupo-ia.html` — documentos de origen.
