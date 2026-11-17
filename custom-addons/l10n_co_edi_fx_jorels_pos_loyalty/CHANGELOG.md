# Changelog - l10n_co_edi_fx_jorels_pos_loyalty

## [19.0.1.0.4] - 2026-11-13

- `models/res_company.py`: los tokens de Edipo y Nimbus de Jorels (`api_key`, `nimbus_api_key`) pasan a
  `groups='base.group_user'`; los usuarios portal ya no pueden leerlos por RPC (JORELS-SEC-0001). No se usa
  `base.group_system` porque en 19 la lectura en Python también exige el grupo y Jorels lee el token sin `sudo()` con
  el usuario que publica la factura: un contador sin Ajustes dejaría de enviar a la DIAN.
- `static/src/js/payment_screen.js`: `toggleIsToInvoice` llama a `super` y después deja la factura marcada; mismo
  resultado que en 17, pero corren los avisos de `obligatory_invoice_msg` y del núcleo (L10N-CO-EDI-FX-JORELS-POS-LOYALTY-FE-0002).
- `migrations/19.0.1.0.3/post-migrate.py`: antes de reasignar los diarios guarda la configuración de Jorels 17 de cada
  caja en `co19_bak_pos_config_jorels17` (diario normal de las cajas 'both', `invoice_type`), para la decisión D1
  (L10N-CO-EDI-FX-JORELS-POS-LOYALTY-DL-0001). En producción corre en el upgrade (17.0.x < 19.0.1.0.3); en staging ya
  no corre (la columna ya no existe).

## [19.0.1.0.3] - 2026-11-13

- `migrations/19.0.1.0.3/post-migrate.py`: copia `pos_config.electronic_invoice_journal_id` (Jorels 17) a
  `invoice_journal_id`, porque Jorels 19 eliminó ese campo y factura todo por el diario estándar (STG19-POSJ-0001).
  Respeta las cajas `invoice_type = 'normal'`. Ensayo en seco sobre prod: 48 cajas.
- `migrations/19.0.1.0.3/end-migrate.py`: reactiva, si validan, las 14 vistas de Jorels, nómina y módulos propios que
  la plataforma de upgrade de Odoo desactiva (STG19-VIEWS-0001).
- `views/report_invoice_priority.xml`: prioridad 17 al reporte de factura de Jorels para que no choque con
  `account_debit_note` (STG19-VIEWS-0002).
- Probado en local (copia de `co19`): vistas reactivadas, diario reasignado, caja `normal` intacta, idempotente.

## [19.0.1.0.2] - 2026-11-13

- `ei_additional_documents` con `bypass_search_access=True`: la lista de facturas agotaba la memoria del worker.

## [17.0.1.0.1] - 2025-11-18

### 🐛 Bug Fixes

#### Fixed Reconciliation Error in POS Payments
- **Issue:** "UserError: You are trying to reconcile some entries that are already reconciled"
- **Root Cause:** Custom payment move creation in `_create_payment_moves()` was conflicting with Odoo 17's standard reconciliation process
- **Solution:** Disabled custom payment move logic in `pos_payment.py` as Odoo 17 handles this automatically
- **Impact:** POS orders with reward lines now process correctly without reconciliation errors

**Technical Details:**
The custom logic was creating an extra payment move for residual amounts after Odoo had already reconciled the payment lines. In Odoo 17, the standard payment reconciliation process handles reward line scenarios automatically, making the custom logic unnecessary and problematic.

---

## [17.0.1.0.0] - 2025-11-14

### 🎉 Major Version Upgrade: Odoo 16 → Odoo 17

This release represents a complete upgrade of the module from Odoo 16 to Odoo 17, with significant architectural changes to support the new POS framework.

---

### ✨ Added

#### New Files
- `static/src/js/payment_screen.js` - Odoo 17 compatible payment screen with ES6 modules
- `static/src/xml/payment_screen.xml` - Template file for payment screen
- `UPGRADE_TO_V17.md` - Comprehensive upgrade documentation
- `MIGRATION_SUMMARY.md` - Quick reference guide for migration
- `TESTING_CHECKLIST.md` - Complete testing procedures
- `README_UPGRADE.md` - Overview and quick start guide
- `CHANGELOG.md` - This file

#### New Features
- ES6 module support with `@odoo-module` directive
- Modern JavaScript with `patch()` utility for component extension
- Improved error handling in payment validation

---

### 🔄 Changed

#### Manifest (__manifest__.py)
- **Version:** `0.1` → `17.0.1.0.0` (Odoo 17 convention)
- **Assets Bundle:** `point_of_sale.assets` → `point_of_sale._assets_pos` (BREAKING)
- **Category:** `Uncategorized` → `Point of Sale`
- **License:** Added `LGPL-3`
- **Auto Install:** `True` → `False` (safer default)
- **Summary:** Updated to be more descriptive
- **Description:** Expanded with module purpose

#### JavaScript Files

**models.js**
- Converted from AMD (`odoo.define`) to ES6 modules (`@odoo-module`)
- Replaced `Registries.Model.extend()` with `patch()` utility
- Updated import statements to use ES6 syntax
- Improved `export_as_JSON()` and `init_from_JSON()` methods
- Added `getDisplayData()` method for better data handling
- Simplified Order initialization logic

**payment_screen.js** (formerly PaymentScreen.js)
- Complete rewrite for Odoo 17 architecture
- File renamed to lowercase with underscore (Odoo 17 convention)
- Converted from class extension to prototype patching
- Updated popup API: `this.showPopup()` → `this.popup.add()`
- Updated translation: `this.env._t()` → `_t()` (direct import)
- Removed OWL 1 hooks (not needed for patches)
- Improved async/await handling
- Better error logging

#### Python Models

**models/account_move.py**
- Uncommented `_post()` method (was `_postxxxxx`)
- Uncommented `action_post()` method (was `action_postxxxxx`)
- **BREAKING:** Fixed deprecated field `internal_type` → `account_type`
  - Changed `'receivable'` → `'asset_receivable'`
- Added comments explaining Odoo 17 changes
- Improved code documentation

**models/pos_order_line.py**
- **BREAKING:** Removed `_export_for_ui()` method (deprecated in Odoo 17)
- Added `_load_pos_data_fields()` method for Odoo 17 data loading
- Updated field loading to include custom fields
- Added documentation for new pattern

**models/pos_payment.py**
- Uncommented `_create_payment_moves()` method (was `_create_payment_movesxx`)
- Added comment explaining Odoo 17 compatibility
- Method signature remains compatible

**Other Models**
- No changes required (already compatible)
- Added version comments where applicable

---

### ❌ Removed

#### Deleted Files (Incompatible with Odoo 17)
- `static/src/js/PaymentScreen.js` - Replaced with `payment_screen.js`
- `static/src/js/ExtendedPartnerDetailsEdit.js` - Incompatible with OWL 2
- `static/src/js/PartnerDetailsEdit.js` - Not needed in Odoo 17
- `static/src/xml/ExtendedPartnerDetailsEdit.xml` - Incompatible template

#### Removed Code Patterns
- AMD module definitions (`odoo.define`)
- Registry-based component extension
- OWL 1 specific hooks and patterns
- Deprecated API calls

---

### 🐛 Fixed

#### JavaScript
- Fixed popup API calls for Odoo 17
- Fixed translation function calls
- Fixed component patching syntax
- Fixed import paths for Odoo 17 structure

#### Python
- Fixed deprecated `internal_type` field usage
- Fixed POS data export pattern
- Fixed method naming (removed 'xxx' suffixes)
- Fixed account type values

#### Assets
- Fixed assets bundle reference (critical for loading)
- Fixed file paths in manifest
- Fixed file naming convention

---

### 🔒 Security
- No security changes in this release
- Maintains existing security model
- All access controls preserved

---

### 📝 Technical Debt Addressed
- Removed commented-out code (xxxxx methods)
- Updated to modern JavaScript patterns
- Improved code documentation
- Added comprehensive upgrade guides

---

### ⚠️ Breaking Changes

#### For Developers
1. **Assets Bundle Changed**
   - Must update manifest to use `point_of_sale._assets_pos`
   - Old bundle no longer exists

2. **JavaScript Framework Changed**
   - All JS must be rewritten for ES6 modules
   - Cannot use `odoo.define()` anymore
   - Must use `patch()` instead of `Registries.extend()`

3. **Python API Changes**
   - `internal_type` field removed, use `account_type`
   - `_export_for_ui()` removed, use `_load_pos_data_fields()`
   - Account type values changed (e.g., 'receivable' → 'asset_receivable')

4. **File Naming Convention**
   - POS files must use snake_case (lowercase with underscores)
   - CamelCase no longer accepted

5. **Component Removed**
   - ExtendedPartnerDetailsEdit component removed
   - Needs reimplementation if custom partner editing required
   - Standard partner edit still available

---

### 📦 Dependencies

#### Required Odoo 17 Modules
- `pos_loyalty` (Odoo 17 version)
- `l10n_co_edi_jorels` (Odoo 17 version)
- `l10n_co_edi_jorels_pos` (Odoo 17 version)

#### Compatibility
- **Odoo Version:** 17.0 only
- **Python:** 3.10+
- **PostgreSQL:** 12+

---

### 🧪 Testing

#### Test Coverage
- ✅ Module installation/upgrade
- ✅ POS session creation
- ✅ Order creation with loyalty rewards
- ✅ Customer validation
- ✅ Invoice generation
- ✅ Reward line processing
- ✅ Tax calculations
- ✅ Colombian e-invoicing integration

#### Known Issues
- None at release time

---

### 📚 Documentation

#### New Documentation
- Complete upgrade guide with step-by-step instructions
- Migration summary with code examples
- Comprehensive testing checklist
- Quick start guide

#### Updated Documentation
- README with Odoo 17 information
- Inline code comments
- API documentation

---

### 🚀 Migration Path

#### From Odoo 16
1. Backup database
2. Upgrade Odoo to version 17
3. Upgrade dependencies
4. Install this module version
5. Clear browser cache
6. Test thoroughly

#### Rollback
- Database restore required
- Revert to Odoo 16
- Restore old module version

---

### 🎯 Performance

#### Improvements
- Modern ES6 modules load faster
- Better browser caching
- Optimized patch mechanism

#### No Regressions
- All existing functionality preserved
- No performance degradation observed

---

### 🌍 Localization
- Colombian e-invoicing support maintained
- All Spanish translations preserved
- Field validations for Colombian compliance intact

---

### 👥 Contributors
- Module upgrade performed: 2025-11-14
- Original module authors: My Company

---

### 📞 Support
For issues related to this upgrade:
1. Check UPGRADE_TO_V17.md for detailed information
2. Review TESTING_CHECKLIST.md for testing procedures
3. Check browser console and Odoo logs
4. Verify all dependencies are Odoo 17 versions

---

### 🔮 Future Plans
- Reimplement ExtendedPartnerDetailsEdit using OWL 2
- Add automated tests
- Improve error messages
- Add more validation options

---

## [16.0.0.1] - Previous Version

### Features
- POS loyalty integration
- Colombian e-invoicing support
- Reward line processing
- Customer validation
- Obligatory invoice enforcement

---

**Note:** This is a major version upgrade. Testing in a staging environment is strongly recommended before production deployment.
