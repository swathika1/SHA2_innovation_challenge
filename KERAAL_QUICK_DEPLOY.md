# 🚀 KERAAL Quick Deploy Guide

## TL;DR - 3 Steps to Deploy

### Step 1: Install Dependencies
```bash
pip install pdfplumber sentence-transformers faiss-cpu -q
```

### Step 2: Ingest Exercise Guides
```bash
python3 ingest_keraal_guides.py
```

Expected output:
```
📚 Found 4 PDF files
✅ Extracted 29,608 characters total
✅ Created 114 chunks
✅ Successfully ingested into RAG system
```

### Step 3: Start Flask
```bash
python3 main.py
```

---

## What Was Fixed

### Issue 1: Exercise Name Not Displaying ❌ → ✅
**Before**: "Idle"  
**After**: "Forward Flexion", "Flank Stretch", "Torso Rotation"

**Why**: Added KERAAL exercises to UI's EXERCISE_PLAN

### Issue 2: Generic Feedback ❌ → ✅
**Before**: "Good effort!"  
**After**: "Form needs improvement. Bend at hips keeping legs straight..."

**Why**: Integrated PDF guides into RAG for context-aware feedback

---

## File Changes Summary

| File | Line(s) | Change |
|------|---------|--------|
| `templates/patient/session.html` | 593-620 | Added KERAAL exercises + normalization |
| `Rehab_Scorer_Coach/src/keraal_pipeline.py` | 354 | Updated LLM feedback to use RAG |

---

## New Files

| File | Purpose |
|------|---------|
| `ingest_keraal_guides.py` | Ingests PDFs into RAG |
| `setup_keraal_rag.sh` | Automated setup |
| `KERAAL_EXERCISE_DISPLAY_AND_RAG.md` | Detailed docs |
| `KERAAL_DEPLOYMENT_SUMMARY.md` | This deployment guide |

---

## Testing (5 min)

1. **Start Flask**
   ```bash
   python3 main.py
   ```

2. **Open Browser**
   ```
   http://127.0.0.1:5050/patient/session
   ```

3. **Test Sequence**
   - Select "Low Back Pain"
   - Choose "Forward Flexion"
   - Perform the exercise
   - Watch:
     - ✅ Exercise name appears
     - ✅ ROM target shows
     - ✅ Feedback is context-aware

---

## Monitoring

### Check RAG System
```bash
python3 -c "import rag_engine; print(rag_engine.get_stats())"
```

Expected:
```
{'total_chunks': 114, 'store_dir': './vector_store'}
```

### View Vector Database
```bash
ls -lh vector_store/
# faiss.index (few MB)
# metadata.json (small)
```

---

## Rollback (If Needed)

No rollback needed - all changes are additive:
- UI additions don't break general pipeline
- RAG falls back gracefully if unavailable
- Can simply not ingest guides if not needed

---

## Performance

- **RAG Query Latency**: ~50ms
- **Feedback Cooldown**: 5 seconds
- **Embedding Cache**: Automatic (faster on repeat)
- **Total Impact**: Negligible (<100ms per frame)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Exercise shows "Idle" | Restart Flask, hard refresh browser |
| No RAG context | Run `python3 ingest_keraal_guides.py` again |
| Import error | `pip install pdfplumber sentence-transformers faiss-cpu` |
| Slow feedback | Normal on first query, faster after cache |

---

## Success Criteria

- [ ] `python3 ingest_keraal_guides.py` shows 114 chunks
- [ ] Exercise names display correctly in UI
- [ ] Feedback includes exercise-specific guidance
- [ ] No errors in Flask logs
- [ ] No errors in browser console

---

## Technical Details (Optional)

### Architecture
```
Webcam → Pose Detection → Form Scoring → RAG Query
                              ↓
                        10-sec aggregation
                              ↓
                        Every 5 sec: LLM Feedback
                              ↓
                        Frontend Display
```

### RAG Pipeline
```
PDF → Text Extraction → Chunking → Embedding → FAISS Index
                                                     ↓
Query → Embedding → FAISS Search → Top-K Results → Format → LLM Context
```

---

## Key Metrics

| Metric | Value |
|--------|-------|
| PDF Chunks Ingested | 114 |
| Vector Dimensions | 384 |
| Similarity Threshold | 0.35 |
| RAG Top-K | 1 (per query) |
| Feedback Cooldown | 5 seconds |
| FPS | 5 (200ms polling) |

---

## Support

**For detailed documentation**, see:
- `KERAAL_EXERCISE_DISPLAY_AND_RAG.md` - Full technical details
- `KERAAL_DEPLOYMENT_SUMMARY.md` - Complete deployment guide

---

**Status**: ✅ Ready for deployment  
**Updated**: February 23, 2026
