APP_CSS = """
#uploaded-tests-panel .uploaded-tests {
  max-height: calc(100vh - 260px);
  overflow: auto;
  border: 1px solid rgba(0,0,0,0.12);
  border-radius: 10px;
  padding: 10px 12px;
  background: rgba(255,255,255,0.7);
}
#uploaded-tests-panel .uploaded-tests__summary {
  margin-bottom: 10px;
  color: rgba(0,0,0,0.7);
  font-size: 0.95rem;
}
#uploaded-tests-panel details.uploaded-tests__group {
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 10px;
  padding: 6px 10px;
  margin: 8px 0;
  background: rgba(255,255,255,0.9);
}
#uploaded-tests-panel summary.uploaded-tests__group-title {
  cursor: pointer;
  font-weight: 600;
  list-style: none;
}
#uploaded-tests-panel summary.uploaded-tests__group-title::-webkit-details-marker { display: none; }
#uploaded-tests-panel .uploaded-tests__badge {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 8px;
  border-radius: 999px;
  background: rgba(0,0,0,0.06);
  font-size: 0.85rem;
  font-weight: 600;
}
#uploaded-tests-panel ul.uploaded-tests__files {
  margin: 8px 0 0 18px;
}
#uploaded-tests-panel li.uploaded-tests__file {
  margin: 2px 0;
}
"""

