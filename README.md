# AGroup website prototype

AGroup is an interior design platform prototype for the CSIT314 group project. It includes a customer website and a portal wireframe for **User Admin, Platform Management, Helpdesk and Interior Designer**.

Platform Management now uses the existing HTML/CSS/JavaScript interface with an object-oriented **Python/Flask backend and local SQLite persistence**. All 14 revised Platform Management stories have working local flows, with category deletion and a Deleted categories page added to the workspace. The group’s target stack is **Python/Flask with Firestore**. Firestore and group authentication remain integration work for the shared application.

## Run the local application

From the `AGroup` folder, prepare the Python environment and start the application.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

The prepared environment can be reused by running the last command. Stop the server with **Ctrl+C**.

- [Platform Management workspace](http://127.0.0.1:8000/portal.html#management/overview)
- [Customer website](http://127.0.0.1:8000/index.html)

The first launch creates `instance/agroup.sqlite3` with 8 categories, 120 fictional projects and 3,600 recorded sample activities. Later launches retain saved changes. The sample includes overlapping Modern and Modern Style assignments for demonstrating a merge, an archived Retro category and an unused Industrial category.

Use the Flask application for Platform Management. The static preview command in the original prototype notes serves the HTML files only.

Run the backend checks from the same folder.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Folder structure

```text
AGroup/
├── index.html       Customer page structure
├── customer.js      Customer views and interactions
├── portal.html      Staff/designer portal structure
├── portal.js        Shared portal routing and other role previews
├── management.js    Platform Management boundary classes
├── management.css   Management layout and featured category styling
├── api.js           Shared API client and request protection
├── app.py           Flask routes and local development server
├── requirements.txt Python dependency
├── backend/         BCE controllers, entities, storage and sample data
├── tests/           Backend regression checks
├── instance/        Generated local database and session secret, ignored by Git
├── data.js          Shared sample data and utility functions
├── styles.css       Customer styling and shared components
├── portal.css       Portal-specific styling
├── assets/
│   ├── living.jpg
│   ├── kitchen.jpg
│   ├── dining.jpg
│   └── bedroom.jpg
├── README.md        This file-by-file development guide
└── README.txt       Original prototype notes, limitations and image sources
```

## Platform Management implementation

| Area | Implementation |
| --- | --- |
| Boundary | `CategoryManagementPage`, `DeletedCategoriesPage`, `CategoryUsagePage` and `ActivityReportPage` in `management.js`. |
| Control | The fourteen original use-case controllers plus `DeleteCategoryController` and `ViewDeletedCategoriesController` in `backend/controllers.py`. |
| Entity | `ProjectCategory`, `ProjectCategoryAssignment`, `InteriorDesignProject`, `ProjectActivity` and `ActivityReport` in `backend/entities.py`. |
| Persistence | Schema and transaction handling in `backend/storage.py`. |
| Sample records | `backend/seed.py` and `backend/sample_projects.json`. Initial project details come from the existing prototype. |
| HTTP integration | `app.py` exposes JSON routes used by `api.js`. |

Python operation names use snake_case. Class names and responsibilities correspond to the class diagram.

| User story | Working behaviour |
| --- | --- |
| View categories | Lists categories with current project counts, status and featured setting. |
| Create category | Saves a new category and checks trimmed, case-insensitive name uniqueness. |
| Edit category | Updates its name and description, with stale-edit detection. |
| Archive category | Keeps existing assignments, blocks new assignments through the entity method and clears featuring. |
| View a period report | Calculates projects created, views, favourite additions and enquiries from persisted records. |
| View category usage | Shows current assignments and all-time recorded activity. |
| Restore category | Makes an archived category active again. |
| Feature category | Updates the featured category buttons on customer discovery when that page loads. |
| Search categories | Supports partial name matching and status filters. |
| Merge categories | Transfers assignments, removes duplicate links and marks the source merged in one database transaction. |
| Review associated projects | Displays the actual assigned projects and the target of a merged category. |
| Filter reports | Applies a category filter to the selected period. |
| Compare periods | Shows both values, absolute differences and percentage changes. Zero baselines produce N/A. |
| Export report | Downloads a CSV from the saved report snapshot, preserving the displayed values and labels. |
| Delete an unused or merged category | Moves a category with zero assigned projects to Deleted categories. |
| View deleted categories | Lists deletion dates, previous statuses and merge destinations, with name search. |

Reports use Singapore time. Weeks run Monday to Sunday and months follow calendar boundaries. Period starts are inclusive and ends are exclusive. Favourite additions count recorded save actions. Filters use current category assignments, so a merge can change historical category totals while retaining the underlying events.

The customer page loads categories and projects from `/api/catalog` when the application server is running. Project openings, favourite additions and enquiries linked to the selected project and its designer produce activity events. A general studio enquiry without a project reference is outside these project activity figures. The customer enquiry itself continues to use the existing local enquiry demonstration.

Management mutations include the category version from the displayed form. A stale version returns a conflict so a later edit can be reviewed before retrying. Activity event IDs prevent a retried submission from being counted twice. Failed merge writes roll back their assignment changes.

### Delete a category after merging

1. Merge the old source category into the target category.
2. In Project categories, select **Delete** on the merged source row, or open **Manage** and select **Delete category**.
3. Confirm the deletion.
4. Open **Deleted categories** in the sidebar to see the retained record, its deletion date and the target category.

Deletion is available when the category has zero assigned projects. An unused active or archived category is also eligible. If a category contains projects, the interface explains that its projects need to be merged first. Archived categories must be restored before that merge.

The category record gains a `deleted_at` timestamp and its featured flag is cleared. The main directory, category usage, customer discovery and new report selections exclude deleted entries. Their previous status and merge destination remain available in the deleted history. Project assignments under the target and previously generated report snapshots retain their values. Category names stay unique across current and deleted entries.

Starting the updated application automatically adds the deletion field to an existing local database. Existing category, project, assignment and activity records are preserved. Restart Flask after updating the source files, then refresh the browser.

### Merge sequence mapping

The merge flow follows the participants and message order on page 03 of the sequence diagram.

| Sequence message | Implementation |
| --- | --- |
| `confirmMerge(sourceId, targetId)` | `CategoryManagementPage.confirmMerge()` in `management.js` forwards the confirmed selection through the API. |
| `mergeCategories(sourceId, targetId)` | `MergeCategoriesController.merge_categories()` coordinates the operation. |
| `findPair(sourceId, targetId)` | The controller calls `ProjectCategory.find_pair()` to retrieve both categories. |
| Valid-selection guard | The controller checks that the categories are different and active, then checks the submitted versions. Invalid selections return an error before mutation. |
| `mergeInto(sourceId, targetId)` | The controller calls `ProjectCategory.merge_into()` inside the open database transaction. |
| `reassign(sourceId, targetId)` | The category entity asks `ProjectCategoryAssignment.reassign()` to transfer assignments and remove duplicate links. |
| `markMerged(sourceId, targetId)` | The category entity calls its internal `_mark_merged()` operation to update the source status, merge destination and featured flag. |
| `MergeResult` and confirmation | The entity returns the target and assignment counts. After the transaction commits, the API returns the result and the boundary displays confirmation. |

The controller's transaction covers retrieval, validation and mutation. A database error rolls back the entire merge. The target keeps its name, description and featured state. Projects and activity records retain their identities. Category versions provide an additional check for changes made after the form was opened.

The local application uses the development access boundary described below. The diagram's authenticated Platform Management session precondition remains part of the group's authentication integration.

### Main API routes

| Route | Purpose |
| --- | --- |
| `GET /api/session` | Local settings and the request protection token. |
| `GET /api/management/categories` | Category list with optional `search` and `status` parameters. |
| `POST /api/management/categories` | Create a category using `name` and `description`. |
| `DELETE /api/management/categories/<id>` | Move an eligible category to Deleted categories using its current `version`. |
| `GET /api/management/categories/deleted` | List deleted categories with an optional `search` parameter. |
| `PATCH /api/management/categories/<id>` | Edit using `name`, `description` and `version`. |
| `POST /api/management/categories/<id>/archive` | Archive using `version`. |
| `POST /api/management/categories/<id>/restore` | Restore using `version`. |
| `POST /api/management/categories/<id>/feature` | Set `featured` using `version`. |
| `POST /api/management/categories/merge` | Merge using `sourceId`, `targetId`, `sourceVersion` and `targetVersion`. |
| `GET /api/management/categories/usage` | Usage summaries for each category. |
| `GET /api/management/categories/<id>/projects` | Associated project records. |
| `POST /api/management/reports` | Generate a report using `period`, `date` and optional `categoryId`. |
| `POST /api/management/reports/compare` | Compare using `period`, `baselineDate`, `comparisonDate` and optional `categoryId`. |
| `GET /api/management/reports/<id>/export` | Export a saved report snapshot. |
| `GET /api/catalog` | Customer project records and active categories. |
| `POST /api/activity` | Record an event using `projectId`, `type` and a unique `eventId`. |

The API client sends the session request token in the `X-CSRF-Token` header for changes. The local development server binds to `127.0.0.1` and accepts local requests. Role switching remains a workspace preview. The group's authenticated user and role checks must be connected for shared hosting.

### Firestore integration

The local implementation uses SQLite as requested for the first runnable version. The entity persistence currently contains SQL queries. Connecting Firestore requires replacing those persistence operations with Firestore collection reads and transactions, including atomic name uniqueness and category merging. Keep the existing controller interfaces and JSON route contracts when integrating the group database.

The assignment data and activity records must be shared with the designer and customer modules. `ProjectCategoryAssignment.assign()` enforces active-category eligibility for new assignments. Group project creation should call the corresponding entity operation. Group activity producers should reuse a stable event ID when retrying a view, save or project enquiry event.

## What each file does

### `index.html` — customer page structure

[index.html](index.html) is the starting page for customers. It contains the AGroup navigation, homepage introduction, footer and containers used by the customer interface.

Important elements:

- `#hero`: the homepage introduction and main photograph.
- `#workspace`: the area where JavaScript inserts project browsing, saved projects, designer profiles or the moodboard.
- `#modal` and `#modal-content`: the dialog used for details and forms.
- `#toast`: short feedback messages, such as confirmation that a project was saved.

It loads the shared styles and category discovery styles, followed by `data.js`, `api.js` and `customer.js`. The scripts use `defer`, so the HTML is parsed before they execute.

**Edit this file to change:** the logo markup, navigation, homepage wording, footer or permanent page structure. Most project cards and forms are generated in `customer.js`, so they will not appear directly in this HTML file.

### `customer.js` — customer behaviour and generated screens

[customer.js](customer.js) creates the dynamic customer screens and responds to clicks, form submissions and changes to the URL fragment after `#`.

| Area | Main functions | Responsibility |
| --- | --- | --- |
| Navigation | `route()` | Selects which customer view to display. |
| Project browsing | `renderExplore()`, `filterResults()`, `card()` | Creates project cards and applies search/filter selections. |
| Project details | `showProject()` | Displays the gallery, materials, estimated cost and enquiry action. |
| Saved projects | `renderSaved()`, `updateCount()` | Displays favourites and updates the navigation count. |
| Designer discovery | `renderDesigners()`, `firm()`, `compare()` | Displays studios, their sample work and comparisons. |
| Moodboard | `renderBoard()` | Displays saved inspiration, notes, a colour and an optional uploaded image. |
| Enquiries | `consult()`, `inquiries()` | Displays the request form and locally stored enquiries/replies. |
| Customer preferences | `profile()`, `preferences()` | Displays demo profile and notification settings. |
| Dialogs and persistence | `show()`, `close()`, `persist()` | Opens/closes dialogs and saves browser-local state. |

Examples of customer navigation:

```text
index.html#explore
index.html#designers
index.html#saved
index.html#moodboard
index.html#project-1
```

Buttons generally use a `data-action` attribute. A shared click handler checks that attribute to decide what to do. Form handlers save demo state and update the relevant screen.

**Edit this file to change:** customer interactions, dynamically generated forms/cards, filtering, favourites or the moodboard. Change the actual sample project details in `data.js` instead.

### `portal.html` — staff/designer portal structure

[portal.html](portal.html) provides the shared layout used by all four portal roles. It contains the sidebar, role selector, navigation container, breadcrumb, content area and dialog.

Important elements:

- `#role-switch`: selects the role being previewed.
- `#portal-nav`: receives the selected role's navigation links.
- `#breadcrumb`: displays the current role and section.
- `#portal-main`: receives dashboards, tables, reports and forms.
- `#modal` and `#modal-content`: display record details and action forms.

It loads the shared and portal styles, then `data.js`, `api.js`, `management.js` and `portal.js`.

**Edit this file to change:** the portal's permanent layout, branding, role selector or footer. Role-specific screens are generated in `portal.js`.

### `portal.js` — portal views and simulated workflows

[portal.js](portal.js) defines the navigation, sample records, tables, forms and interactions for each role.

The main configuration/data sections are:

| Section | Purpose |
| --- | --- |
| `configs` | Defines each role's name, navigation, introduction and sample dashboard statistics. |
| `sample` | Holds fictional tickets, companies, projects, proposals, reviews and other records. |
| `actions` | Defines the actions offered when a record is opened. |
| `categories` | Loads saved demo categories or creates the initial sample category list. |

The main functions are:

| Functions | Responsibility |
| --- | --- |
| `route()`, `overview()` | Select the role/section and render its dashboard. |
| `recordPage()`, `filterRecords()`, `openRecord()` | Display searchable records and their details. |
| `recordAction()`, `log()`, `historyPage()` | Record demo decisions and display local activity history. |
| `categoryPage()`, `filterCategories()`, `categoryForm()` | Display, search, create and edit categories. |
| `mergeForm()` | Display the category merge form; its submission handler previews the status change. |
| `usage()` | Display illustrative category usage figures. |
| `reportPage()`, `buildReport()` | Display reporting controls and generate sample report/comparison figures. |
| `company()` | Display the designer's company profile and qualification-upload preview. |
| `pending()` | Explain designer stories that still require client confirmation. |

Platform Management routes delegate to `management.js` and its API-backed boundary classes. The original category and report helpers in `portal.js` belong to the prototype implementation. Designer analytics still uses its sample reporting view.

Each role has these screens:

| Role | Screens |
| --- | --- |
| User Admin | Overview, company verification, escalated tickets, listings/reviews, accounts/appeals, decision history. |
| Platform Management | Overview, project categories, category usage, activity reports, period comparison. |
| Helpdesk | Overview, active tickets, resolved tickets, complaints/listings, verification recommendations, upload diagnostics. |
| Interior Designer | Overview, company/qualifications, projects, enquiries, proposals/feedback, reviews, analytics, pending scope. |

Examples of portal navigation:

```text
portal.html#admin/verification
portal.html#management/categories
portal.html#helpdesk/tickets
portal.html#designer/enquiries
```

**Edit this file to change:** portal menus, record fields, available actions, category forms or reporting previews. The role selector is a demonstration tool, not authentication or permission enforcement.

### `data.js` — shared data and helpers

[data.js](data.js) creates the shared `window.AG` object used by both JavaScript files.

| Property/helper | Purpose |
| --- | --- |
| `projects` | Six fictional projects, including style, location, budget, materials and image name. |
| `firms` | Three fictional interior design companies and their sample profile information. |
| `escape(value)` | Escapes special HTML characters when inserting text into generated HTML. |
| `money(value)` | Formats a number as a Singapore-dollar amount. |
| `read(key, fallback)` | Reads JSON from browser storage, using the fallback when necessary. |
| `write(key, value)` | Saves JSON to browser storage and returns whether the write succeeded. |
| `toast(message)` | Displays a temporary status message in `#toast`. |

For example, `AG.write('saved', [1, 4])` stores the saved project IDs under `agroup-saved`.

**Edit this file to change:** customer sample projects, company profiles, currency formatting or shared storage helpers. Portal ticket/category data is defined separately in `portal.js`; changing `data.js` does not automatically update every portal record or counter.

### `styles.css` — customer styling and shared components

[styles.css](styles.css) controls the customer website's appearance and provides components reused by the portal.

It includes:

- CSS variables for colours and spacing-related design choices.
- Typography, buttons, inputs, tables, dialogs and feedback messages.
- Homepage layout, project cards, filters, designer cards and moodboard layout.
- Responsive rules for smaller screens.
- Keyboard focus styles and reduced-motion support.

**Edit this file to change:** the customer theme, shared buttons/forms or responsive customer layouts. Because the portal also loads this file, check both pages after changing shared selectors such as `.button`, `table`, `input` or `dialog`.

### `portal.css` — portal-specific styling

[portal.css](portal.css) adds the monochrome portal appearance and overrides relevant shared styles from `styles.css`.

It controls the sidebar, top bar, dashboard statistics, panels, record tables, status labels, placeholder charts and responsive portal layout. Many overrides are scoped beneath `.portal-body` so they apply to the portal only.

**Edit this file to change:** portal spacing, sidebar size, dashboard layout, tables or mobile behaviour. Keep portal-specific changes scoped to avoid affecting the customer website.

### `assets/` — illustrative photographs

The four JPEG files supply imagery for the homepage, project cards, galleries and moodboards.

| File | Used for |
| --- | --- |
| `living.jpg` | Homepage photograph and living-space inspiration. |
| `kitchen.jpg` | Kitchen inspiration in cards and galleries. |
| `dining.jpg` | Dining/interior inspiration in cards and galleries. |
| `bedroom.jpg` | Bedroom/interior inspiration in cards and galleries. |

Project records use an image name without the extension, such as `image: 'living'`. The JavaScript constructs `assets/living.jpg` from that value.

**To replace an image:** keep its existing filename, or update the corresponding references in the HTML/JavaScript. If adding a new filename, also check the gallery image lists in `customer.js`. Image source URLs are recorded in [README.txt](README.txt).

### `README.txt` — original handover notes

[README.txt](README.txt) contains the original setup guide, feature overview, limitations, source alignment, verification notes and image-source URLs. This Markdown guide expands the explanation of the individual files for your group.

## How the files work together

| Customer website | Staff/designer portal |
| --- | --- |
| `index.html` supplies the page structure. | `portal.html` supplies the page structure. |
| `styles.css` supplies its appearance. | `styles.css` supplies shared styles; `portal.css` adds portal-specific styles. |
| `data.js` supplies shared sample data/helpers. | `data.js` supplies shared sample data/helpers. |
| `customer.js` inserts customer screens and handles actions. | `portal.js` inserts role-specific screens and handles demo actions. |

The customer and other role demonstrations use browser `localStorage`. Platform Management uses the local database. Browser storage lets the enquiry demonstration share information when both pages run under the same origin: the same protocol, hostname and port. Using `localhost` for one page and `127.0.0.1` for the other creates separate storage locations.

Stored state includes:

| Storage key | Contents |
| --- | --- |
| `agroup-saved`, `agroup-savedSort` | Saved project IDs and their display order preference. |
| `agroup-board` | Moodboard title, notes, colour, selected projects and optional image. |
| `agroup-profile`, `agroup-preferences` | Demo customer profile and notification settings. |
| `agroup-history` | Recently viewed project IDs used for simple suggestions. |
| `agroup-inquiries` | Demo enquiries, statuses and simulated replies. |
| `agroup-categories` | Locally edited category records. |
| `agroup-recordChanges`, `agroup-audit` | Simulated record changes and action history. |
| `agroup-company` | The designer's locally edited company profile. |

Changes are not synchronised between different browsers or devices. Clear only the `agroup-` entries in your browser's local storage when you want to reset this prototype.

## Where to make common changes

| Change you want | File(s) to edit |
| --- | --- |
| Change the homepage heading or navigation labels | `index.html` |
| Add or edit a sample customer project | `data.js`; add its photograph to `assets/` if needed |
| Add a new style/location filter option | `customer.js`, keeping options consistent with `data.js` |
| Change the customer enquiry form | `customer.js` |
| Change project-card layout or colours | `styles.css`; `customer.js` if changing card markup |
| Change portal branding or its permanent structure | `portal.html` |
| Add a portal navigation item and its screen | `configs` and routing/rendering logic in `portal.js` |
| Change sample support tickets or admin records | `sample` in `portal.js` |
| Change the actions available on a portal record | `actions` and the relevant handler in `portal.js` |
| Change category or reporting behaviour | `portal.js` |
| Change the portal's appearance | `portal.css` |
| Change a helper used by both interfaces | `data.js` |

After editing a form or button, check its `id`, field `name` and `data-action` attributes against its JavaScript handler. These attributes connect the displayed interface to its behaviour.

## Try the enquiry workflow

1. Open the customer website and request a consultation with **Form & Field**, using fictional details.
2. Open the portal on the same server and browser.
3. Select **Interior Designer**, then **Leads & enquiries**.
4. Open the new enquiry, select **Reply to enquiry**, enter a response and record the demo action.
5. Return to the customer website and open **My enquiries** to see the reply.

The designer workspace represents Form & Field only. No real message is sent. Enquiries for other fictional studios remain visible to the customer but are not displayed in this designer workspace.

## Current integration status

Platform Management is runnable locally with persisted categories, assignments, activity and report snapshots. The API and entity checks cover the requested category and reporting workflows.

The shared application still needs the group's Firestore persistence and authenticated access. Other role workflows retain their existing prototype behaviour, including company verification, support decisions, project publishing, qualification uploads and customer enquiry records. These modules need their own backend integration.

The recommendation ordering remains the existing style-based demonstration. Customer review publication, public moodboard links and notification delivery remain group implementation work.

Twenty-seven backend regression tests cover category changes, duplicate and concurrent names, stale edits, merge message order, invalid merge guards, rollback at multiple write stages, assignment deduplication, deletion eligibility, deleted-history retention, database migration, report boundaries, comparisons, CSV snapshot consistency, event retries and local request protection. The tests were added during implementation as regression checks.

Browser checks covered category creation, editing, search, duplicate validation, featuring on customer discovery, archiving, restoring, assigned-project review, merging, period reports, comparisons, CSV download, customer activity capture and navigation between roles. The mobile workspace was checked at a 390-pixel viewport. Tables scroll horizontally to expose all columns.

Deletion browser checks covered a blocked deletion with assigned projects, merging and deleting the source, retaining 60 distinct target projects, preserving an exported report, searching deleted history, retaining deleted entries after reload and the mobile history page.
