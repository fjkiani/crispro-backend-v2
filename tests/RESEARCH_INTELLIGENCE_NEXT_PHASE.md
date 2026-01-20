# 🚀 RESEARCH INTELLIGENCE - NEXT PHASE: TESTING & VERIFICATION

**Date**: January 2, 2026  
**Status**: Database Setup Complete → Testing Phase  
**Goal**: Verify all 10 deliverables work end-to-end

---

## ✅ PHASE 1 COMPLETE: Database Setup

- ✅ Supabase schema created and deployed
- ✅ Tables: `research_intelligence_queries`, `research_intelligence_dossiers`
- ✅ RLS policies configured
- ✅ Indexes created
- ✅ Triggers set up

---

## 🧪 PHASE 2: Integration Testing

### **Test 1: Database Connection**
```bash
python3 tests/test_research_intelligence_integration.py
```

**What to Verify**:
- ✅ Supabase client connects successfully
- ✅ Tables are accessible
- ✅ RLS policies are active

### **Test 2: Query Execution**
**What to Verify**:
- ✅ Research Intelligence orchestrator runs
- ✅ Queries execute successfully
- ✅ Results are returned

### **Test 3: Auto-Save (Requires Authenticated User)**
**Manual Test Steps**:
1. Start backend server
2. Make authenticated POST request to `/api/research/intelligence`
3. Verify query saved in Supabase
4. Check `query_id` in response

**Test Request**:
```bash
curl -X POST http://localhost:8000/api/research/intelligence \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How does curcumin help with cancer?",
    "context": {"disease": "breast_cancer"},
    "persona": "patient"
  }'
```

### **Test 4: Dossier Generation**
**What to Verify**:
- ✅ Dossier generated for all personas
- ✅ Markdown content is valid
- ✅ All sections included

### **Test 5: Value Synthesis**
**What to Verify**:
- ✅ Value synthesis generated
- ✅ Persona-specific insights
- ✅ Action items extracted

### **Test 6: Query History API**
**Test Endpoints**:
```bash
# Get history
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/research/intelligence/history?limit=10

# Get specific query
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/research/intelligence/query/{query_id}
```

---

## 🎨 PHASE 3: Frontend Testing

### **Test 7: Query History Sidebar**
**What to Verify**:
1. Navigate to Research Intelligence page
2. Sidebar appears (if authenticated)
3. Recent queries load
4. Search works
5. Click selects query

### **Test 8: Persona Selector**
**What to Verify**:
1. Persona dropdown appears
2. Can switch between Patient/Doctor/R&D
3. Persona sent in API request
4. Results change based on persona

### **Test 9: Value Synthesis Display**
**What to Verify**:
1. After query completes, "What This Means" card appears
2. Patient view shows "Will this help?" and "Is it safe?"
3. Doctor view shows clinical recommendations
4. R&D view shows knowledge gaps
5. Action items displayed

### **Test 10: End-to-End Flow**
**Complete User Journey**:
1. User logs in
2. Navigates to Research Intelligence
3. Sees query history sidebar
4. Selects persona (Patient)
5. Enters question
6. Runs query
7. Sees results with value synthesis
8. Query auto-saved
9. Can view in history
10. Can switch persona and see different view

---

## 🔧 PHASE 4: Production Readiness Checks

### **Backend Checks**
- [ ] Error handling works (non-blocking saves)
- [ ] Rate limiting (if applicable)
- [ ] Logging configured
- [ ] Environment variables set
- [ ] Supabase connection stable

### **Frontend Checks**
- [ ] Loading states work
- [ ] Error messages display
- [ ] Empty states handled
- [ ] Responsive design
- [ ] Accessibility (ARIA labels)

### **Database Checks**
- [ ] RLS policies working (users see only their data)
- [ ] Indexes improve query performance
- [ ] Triggers update timestamps
- [ ] Foreign keys enforce integrity

---

## 📊 SUCCESS CRITERIA

**Phase 2 Complete When**:
- ✅ All integration tests pass
- ✅ Auto-save works for authenticated users
- ✅ Dossier generation works
- ✅ Value synthesis works
- ✅ Query history API works

**Phase 3 Complete When**:
- ✅ Frontend components render
- ✅ Query history sidebar works
- ✅ Persona selector works
- ✅ Value synthesis displays
- ✅ End-to-end flow works

**Phase 4 Complete When**:
- ✅ All production checks pass
- ✅ Error handling verified
- ✅ Performance acceptable
- ✅ Security verified (RLS)

---

## 🚀 QUICK START TESTING

1. **Run Integration Tests**:
   ```bash
   cd oncology-coPilot/oncology-backend-minimal
   python3 tests/test_research_intelligence_integration.py
   ```

2. **Start Backend**:
   ```bash
   # In backend directory
   uvicorn api.index:app --reload
   ```

3. **Start Frontend**:
   ```bash
   # In frontend directory
   npm run dev
   ```

4. **Test Manually**:
   - Navigate to Research Intelligence page
   - Run a query
   - Verify all features work

---

## 📝 NEXT STEPS AFTER TESTING

1. **Fix Any Issues Found**
2. **Performance Optimization** (if needed)
3. **Documentation Updates**
4. **User Acceptance Testing**
5. **Production Deployment**

---

## ✅ READY TO TEST

All code is implemented. Database is set up. Ready for comprehensive testing!

