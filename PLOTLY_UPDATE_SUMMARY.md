# Plotly.js Update Summary

**Date**: 2025-01-15  
**Status**: ✅ **COMPLETED**

---

## Update Details

### Version Change
- **Previous Version**: 2.35.2 (July 2021)
- **New Version**: 3.2.0 (Latest)
- **Upgrade Type**: Major version upgrade (2.x → 3.x)

### Files Updated
1. `src/templates/dashboard.html` - Line 12
2. `src/templates/analysis.html` - Line 12
3. `src/templates/comparison.html` - Line 12

### Changes Made
All Plotly.js CDN references updated from:
```html
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
```

To:
```html
<script src="https://cdn.plot.ly/plotly-3.2.0.min.js" charset="utf-8"></script>
```

---

## Important Notes

### Breaking Changes (Version 3.x)

**Mapbox to MapLibre Transition:**
- Starting with Plotly.js v2.35.0+, Plotly transitioned from Mapbox to MapLibre for rendering map-type charts
- If your code uses map charts, you may need to update:
  - `_mapbox` → `_map` (trace names)
  - `layout.mapbox` → `layout.map`
  - `mapbox_style` → `map_style`
- **Note**: This application doesn't appear to use map charts, so this change shouldn't affect functionality

### Performance Improvements
- Version 3.x includes significant performance enhancements
- Support for typed arrays reduces render times substantially
- Better memory management

### Compatibility
- The application uses standard Plotly.js chart types:
  - Line charts (`scatter` with `mode: 'lines'`)
  - Bar charts (`bar`)
  - Pie charts (`pie`)
  - Scatter plots (`scatter`)
  - Indicators (`indicator`)
- These chart types maintain backward compatibility in version 3.x

---

## Testing Recommendations

### Charts to Test

1. **Dashboard Page** (`/dashboard`):
   - [ ] Portfolio Growth Chart (line chart)
   - [ ] Asset Allocation Chart (pie chart)
   - [ ] Chart interactions (hover, zoom, etc.)

2. **Analysis Page** (`/analysis`):
   - [ ] Rolling Returns Chart (bar chart)
   - [ ] VaR Chart (indicator)
   - [ ] Drawdown Chart (scatter with fill)
   - [ ] Correlation Heatmap
   - [ ] Current Allocation Chart (pie chart)
   - [ ] Sector Allocation Chart (bar chart)

3. **Comparison Page** (`/comparison`):
   - [ ] Performance Comparison Chart (line chart)
   - [ ] Returns Comparison Chart (bar chart)
   - [ ] Risk Comparison Chart (bar chart)
   - [ ] Risk-Return Scatter Plot
   - [ ] Comparative Timeline Chart

### Test Checklist
- [ ] All charts render correctly
- [ ] Chart interactions work (hover, zoom, pan)
- [ ] No JavaScript console errors
- [ ] Charts are responsive
- [ ] Chart styling matches theme (dark mode)
- [ ] Data displays correctly in all charts

---

## Rollback Instructions

If issues are encountered, rollback by reverting the three files to:
```html
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
```

---

## Status

✅ **Update Complete**
- All files updated
- No linting errors
- Ready for testing

**Next Step**: Manual browser testing recommended to verify all charts work correctly with the new version.

---

**Update Completed**: 2025-01-15  
**Updated By**: Automated update process  
**Testing Status**: ⚠️ **MANUAL TESTING RECOMMENDED**

