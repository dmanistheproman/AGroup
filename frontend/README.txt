AGROUP — CUSTOMER WEBSITE & BACKEND PORTAL WIREFRAME
==================================================

START HERE
----------
Customer website: index.html
Partner/staff portal: portal.html

Start the app from the project root (see README.md there):

1. Run: python run.py   (macOS / Linux: python3 run.py)
2. The browser opens the customer website; the terminal prints both addresses.
3. Stop the server with Ctrl+C when finished.

No build step or package installation is required. Keep the HTML, CSS,
JavaScript and assets together when copying the prototype. The included photos
are local files; the pages do not need external fonts, scripts or image services.

WHAT THIS VERSION IS
--------------------
A static HTML/CSS/JavaScript prototype for discussing the customer experience
and the four role-specific workspaces. It is not a deployed application.
Screens backed by the Python/Flask backend call /api/... routes; the rest are
browser-local wireframes. Firestore, authentication and access control are not
implemented yet.
The portal role selector changes the preview; it is not an access-control system.

Firms, projects, ratings, records, prices, documents and analytics are fictional.
Photos are illustrative and do not represent the fictional firms' actual work.
Demo changes use this browser's localStorage, with keys prefixed "agroup-".
Use sample information in the prototype. Clearing those keys resets its state.
The customer sample dataset and portal counters are not a connected database.

CUSTOMER WEBSITE
----------------
- Home page inspired by the discovery journey on Sixides, with original AGroup
  branding, wording, layout and styling.
- Search project cards by text; filter by style, budget, home type and location.
- Project details, illustrative gallery, materials and estimated costs.
- Save/unsave projects and sort favourites by recency or estimated cost.
- Compare studios associated with saved projects.
- Browse fictional company profiles and portfolio examples.
- Demo consultation/quotation request form and enquiry-status view.
- Browser-local profile/preferences form, not real account registration.
- Simple recommendation ordering based on saved/viewed styles and preferences;
  it is not a trained recommendation model.
- Moodboard with saved projects, notes, a colour and one locally stored image.
- Moodboard sharing preview only; no public share link is generated.
- Review form preview only; reviews are not published and project completion
  eligibility is not checked by this prototype.
- Notification preferences are saved locally; no notifications are sent.

BACKEND PORTAL WIREFRAME
-----------------------
Use the PREVIEW AS selector in the sidebar.

User Admin:
Overview; company verification; escalated tickets; listing/review moderation;
account flags and appeals; demo decision history.

Platform Management:
Overview; searchable categories; creation/editing; archive/restore; featured
state; assigned-project preview; category usage; report selection; comparisons;
CSV export. Category merge previews status changes only. Real assignment
transfer, deduplication, transactional writes and metric recalculation remain
backend work. Usage totals and project previews are illustrative.

Helpdesk:
Overview; ticket queue with search/requester/type/status filters; resolved-ticket
search; complaints; verification recommendations; upload diagnostics. Record
panels preview assignment, notes, responses, information requests, duplicate
merging, escalation, hiding listings and closing tickets. These actions record
local demo decisions; they do not perform real support operations.

Interior Designer:
Overview; company profile and qualification upload preview; current/past
portfolio; leads/enquiries with style filtering; proposals/feedback; reviews;
portfolio analytics. The demo studio is Form & Field. Quotation provision,
payment progress and customer credit status are marked as pending client
confirmation, matching the combined user-story file.

Reports:
Date, period and category/project selections generate deterministic SAMPLE
figures, not queries of actual activity. Equal dates with the same selections
produce equal comparison values. The CSV contains the displayed sample values
and selection labels. The chart is a layout placeholder, explicitly labelled.

A CONNECTED DEMO TO TRY
-----------------------
1. On the customer website, open a project and request a consultation.
2. Choose Form & Field and submit using fictional information.
3. Open portal.html on the SAME local server and browser.
4. Switch to Interior Designer, then Leads & enquiries.
5. Open the new enquiry, choose Reply to enquiry, enter a response and record it.
6. Return to the customer website and open My enquiries to see the demo reply.

The same local browser storage enables this demonstration; no external message
is sent. Requests to other fictional studios remain in the customer view, since
this prototype's designer workspace represents Form & Field only.

SOURCE ALIGNMENT
----------------
- COMBINED_USERS_STORIES.md: customer, designer, Helpdesk and User Admin screens.
- UserStories/PlatformManagementUserStory-Changed.txt and the supplied Platform
  Management diagram: category/reporting scope, including featuring categories.
- ProjectSpecification.md: customer/designer platform and role responsibilities.
- Reference: https://www.sixides.com/
  Used for general inspiration browsing and designer-discovery structure.
  No Sixides text, logos, ratings or proprietary verification claims are reused.

FILE ORGANISATION
-----------------
index.html       Customer page shell.
js/customer.js   Customer views, forms and browser-local interactions.
portal.html      Role-based portal shell.
js/portal.js     Portal wireframes and simulated workflows.
js/data.js       Fictional customer data and shared storage/escaping helpers.
css/styles.css   Customer styling and common components.
css/portal.css   Monochrome portal wireframe styling.
js/suspend-account.js  User Admin suspension form and API call.
login.html       Log in page (demo login until the backend login is connected).
js/login.js      Login form checks and demo account buttons.
js/account.js    Shared demo session and the header account menu.
css/login.css    Login page layout.
css/account.css  Header avatar and dropdown menu.
assets/          Local illustrative interior photographs.

NEXT IMPLEMENTATION STEP
------------------------
Keep these screens as boundary prototypes. Introduce Flask routes, Python BCE
controllers/entities and Firestore persistence behind them. Replace demo data
and localStorage with authenticated server requests. Agree shared collection
schemas and permissions before teammates implement separate role modules.

Checks must happen on the server: role permissions, category uniqueness,
transactional merges, review eligibility, document access and report rules.
Use a proper image/document storage service for uploads rather than placing
large file contents in ordinary Firestore records. Choose the service with the
team before implementing uploads.

VERIFICATION
------------
- JavaScript syntax checks passed.
- Local HTTP responses and referenced assets checked.
- DOM-level checks passed for initial rendering, filters, empty results,
  favourites, comparison, moodboard saving and enquiry submission.
- All 25 portal navigation views rendered in DOM checks without runtime errors.
- Category duplicate validation, creation, archive, restore and merge checked.
- Equal-period reporting and customer-to-designer demo replies checked.
- Browser preview service was unavailable. Actual desktop/mobile rendering,
  keyboard behaviour, file picker and browser download UI still need a visual
  check in your browser. Responsive CSS is included but not visually verified.

IMAGE SOURCES
-------------
Illustrative photos downloaded from the Unsplash image CDN:
living.jpg:
https://images.unsplash.com/photo-1600210492486-724fe5c67fb0
kitchen.jpg:
https://images.unsplash.com/photo-1600607687920-4e2a09cf159d
dining.jpg:
https://images.unsplash.com/photo-1600566753086-00f18fb6b3ea
bedroom.jpg:
https://images.unsplash.com/photo-1616486338812-3dadae4b4ace

These images are used only as prototype inspiration, not evidence of completed
projects by the fictional studios.
