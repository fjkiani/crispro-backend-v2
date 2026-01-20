# Frontend Status Summary (Current State)

**Date:** 2026-01-11  
**Status:** ✅ **IO/ESSENTIALITY/PGx SHIPPED** | ❌ **3 ORPHANED CAPABILITIES REMAIN**

---

## ✅ SHIPPED (Zo just completed)

| # | Capability | Backend | Frontend | Status |
|---|-----------|---------|----------|--------|
| 10 | IO Safest Selection | ✅ | ✅ | **SHIPPED (RUO)** |
| 4 | Essentiality Scores | ✅ | ✅ | **WIRED** (audit needs update) |
| N/A | PGx Safety | ✅ | ✅ | **WIRED** (DrugRankingPanel shows `pgx_screening`) |

---

## ❌ REMAINING ORPHANED (Backend ✅, Frontend ❌)

| # | Capability | Backend | Frontend | Priority | Plumber Task |
|---|-----------|---------|----------|----------|--------------|
| 2 | Synthetic Lethality | ✅ | ❌ | **P1** | Create `SyntheticLethalityCard.jsx` + wire API call |
| 3 | VUS Resolution | ✅ | ❌ | **P1** | Vey exists, just needs verification) |
| 8 | Holistic Score | ✅ | ❌ | **P2** | Add chip to trial cards (backend already computes, just render) |

---

## ⚠️ BUGS (Backend issues, NOT frontend)

| # | Capability | Issue | Priority | Status |
|---|-----------|-------|----------|--------|
| 1 | Sporadic Gates | Partial frontend | P0 | Backend bug (field mismatch) |
| 7 | Clinical Trials | Returns 0 | P0 | Backend bug (PLUMBER TASK 1) |
| 5 | Resistance Prophet | Wrong baseline | P1 | Backend bug (not frontend) |

---

## 🔒 LOCKED (Legitimately not available)

| # | Capability | Reason | Status |
|---|-----------|--------|--------|
| 6 | WIWFM Drug Efficacy | Requires NGS (no NGS data) | **LOCKED** |
| 9 | CA-125 Intelligence | Requires CA-125 value (no value) | **LOCKED** |

---

## 📊 PROGRESS

**Total Capabilities:** 10  
**Shipped:** 3 (IO Selection, Essentiality, PGx Safety)  
**Remaining Orphaned:** 3 (Synthetic Lethality, VUS Resolution, Holistic Score)  
**Backend Bugs:** 3 (Sporadic Gates, Cls, Resistance Prophet)  
**Locked:** 2 (WIWFM, CA-125)

**Frontend Completion:** 30% (3/10 shipped)  
**Frontend Remaining:** 30% (3 orphaned)  
**Backend Issues:** 30% (3 bugs)  
**Legitimately Locked:** 20% (2 capabilities)

---

## 🎯 NEXT STEPS FOR PLUMBER

### P1 - HIGH (This Week)

1. **Synthetic Lethality** (see `FRONTEND_DELIVERABLES_FOR_PLUMBER.md`)
   - Create `SyntheticLethalityCard.jsx`
   - Wire API call in `AyeshaCompleteCare.jsx`
   - Render in JSX

2. **VUS Resolution** (see `FRONTEND_DELIVERABLES_FOR_PLUMBER.md`)
   - Verify existing code works
   - Test with PDGFRA p.S755P

### P2 - MEDIUM (This Sprint)

3. **Holistic Score** (see `FRONTEND_DELIVERABLES_FOR_PLUMBER.md`)
   - Add holistic score chip to trial cards
   - No API calls needed (backend already computes)

---

## 📝 FILES TO REFERENCE

- **Frontend Deliverables:** `FRONTEND_DELIVERABLES_FOR_PLUMBER.md` (this directory)
- **Master Audit:** `MOAT_CAPABILITY_AUDIT.md` (parent directory)
- **IO Selection Decisions:** `IO_SAFEST_CTION_AUDIT.md` (this directory)

**Last Updated:** 2026-01-11  
**By:** Zo (Alpha's Agent)
