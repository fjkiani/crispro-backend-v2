# 🎨 MOAT Orchestrator Frontend Architecture

**Status**: 🚧 In Progress (25% Complete)  
**Principle**: Modular, not monolithic

---

## 📁 Component Structure

```
src/
├── components/
│   └── orchestrator/              # NEW: Orchestrator components
│       ├── Dashboard/
│       │   ├── OrchestratorDashboard.jsx
│       │   └── PipelineStatusCard.jsx
│       │
│       ├── Patient/
│       │   ├── PatientUpload.jsx        ✅ Created
│       │   ├── PatientProfileCard.jsx
│       │   └── PatientSummary.jsx
│       │
│       ├── Analysis/
│       │   ├── BiomarkerCard.jsx        ✅ Created
│       │   ├── ResistanceCard.jsx       ⏳ TODO
│       │   ├── DrugRankingCard.jsx      ⏳ TODO
│       │   ├── TrialMatchesCard.jsx     ⏳ TODO
│       │   ├── NutritionCard.jsx         ⏳ TODO
│       │   └── SyntheticLethalityCard.jsx ⏳ TODO
│       │
│       ├── CarePlan/
│       │   ├── CarePlanViewer.jsx       ⏳ TODO
│       │   ├── CarePlanSection.jsx      ⏳ TODO
│       │   └── CarePlanExport.jsx       ⏳ TODO
│       │
│       ├── Monitoring/
│       │   ├── MonitoringDashboard.jsx  ⏳ TODO
│       │   ├── AlertPanel.jsx           ⏳ TODO
│       │   └── BiomarkerChart.jsx       ⏳ TODO
│       │
│       └── common/
│           ├── LoadingState.jsx          ⏳ TODO
│           ├── ErrorState.jsx            ⏳ TODO
│           └── EmptyState.jsx            ⏳ TODO
│
├── services/
│   └── api/
│       └── orchestrator.ts              ✅ Created
│
├── hooks/
│   └── useOrchestrator.ts               ✅ Created
│
└── pages/
    └── OrchestratorDashboard.jsx        ✅ Created
```

---

## 🔌 API Integration Layer

### Service: `orchestrator.ts`

**Methods:**
- `runPipeline()` - Execute full pipeline
- `getStatus()` - Get pipeline status
- `getState()` - Get full patient state
- `processEvent()` - Process trigger events
- `listStates()` - List all patients
- `healthCheck()` - Service health

**Features:**
- ✅ TypeScript types
- ✅ Error handling
- ✅ Configurable API base URL

---

## 🎣 React Hooks

### `useOrchestrator`

**Returns:**
- `state` - Current patient state
- `status` - Pipeline status
- `loading` - Loading state
- `error` - Error state
- `runPipeline()` - Execute pipeline
- `refreshStatus()` - Refresh status
- `refreshState()` - Refresh full state
- `clearError()` - Clear errors

---

## 🎨 Component Patterns

### 1. Self-Contained Components

Each component:
- Manages its own loading/error states
- Accepts props for data
- Handles empty states gracefully
- Is reusable across pages

### 2. Data Flow

```
API Service → React Hook → Component → UI
```

### 3. Error Handling

- Components show error states
- Hooks catch and expose errors
- API service throws typed errors

---

## 📋 Implementation Checklist

### ✅ Completed
- [x] API service layer
- [x] React hook (`useOrchestrator`)
- [x] Patient upload component
- [x] Biomarker card component
- [x] Main dashboard page
- [x] Architecture documentation

### ⏳ In Progress
- [ ] Remaining analysis cards
- [ ] Care plan viewer
- [ ] Monitoring dashboard
- [ ] Navigation/routing
- [ ] Error boundaries
- [ ] Loading states

---

## 🚀 Next Steps

1. **Complete Analysis Cards** (2-3 hours)
   - ResistanceCard
   - DrugRankingCard
   - TrialMatchesCard
   - NutritionCard
   - SyntheticLethalityCard

2. **Care Plan Viewer** (1-2 hours)
   - Section navigation
   - Export functionality
   - Print support

3. **Monitoring Dashboard** (1-2 hours)
   - Alert panel
   - Biomarker charts
   - Timeline view

4. **Integration** (1 hour)
   - Add to main app routing
   - Connect to existing navigation
   - Add to sidebar/menu

---

## 🎯 Design Principles

1. **Modular**: Each component is independent
2. **Reusable**: Components can be used anywhere
3. **Type-Safe**: TypeScript throughout
4. **Accessible**: ARIA labels, keyboard nav
5. **Responsive**: Mobile-friendly layouts
6. **Performant**: Lazy loading, code splitting

---

**Status**: Foundation complete, ready for component expansion! 🚀

