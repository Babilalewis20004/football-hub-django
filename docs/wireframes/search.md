# Search

**Template:** `templates/blog/search_results.html`
**Route:** `/search/?q=<term>` (`blog.views.search.search_posts`, name=`search`)
**Entry point:** the search box in `components/masthead.html` (`method="GET"`, present on every page)
**Users/roles:** Public.

## Wireframe

```text
+----------------------------------------------------------------+
| MASTHEAD (search box: [.....................] [🔍])              |
+----------------------------------------------------------------+
| Search results for "{{ query }}"                                 |
|                                                                    |
| {% if results %}                                                  |
|   +----------+  +----------+  +----------+                        |
|   | [image]  |  | [image]  |  | [image]  |                        |
|   | Title    |  | Title    |  | Title    |                        |
|   | [ Read ] |  | [ Read ] |  | [ Read ] |                        |
|   +----------+  +----------+  +----------+                        |
|   ... (paginated, 10 per page — pagination controls presence not   |
|        independently confirmed in the template markup itself)     |
| {% else %}                                                        |
|   "No results found."                                              |
| {% endif %}                                                       |
+----------------------------------------------------------------+
| FOOTER                                                            |
+----------------------------------------------------------------+
```

Layout uses simpler markup than `category_posts.html`/`tag_posts.html` (matches `author_posts.html`'s plainer style rather than the `posts-grid`/`post-card` pattern).

## Query logic

`Post.objects.filter(Q(title__icontains=query) | Q(content__icontains=query) | Q(category__name__icontains=query) | Q(tags__name__icontains=query), is_published=True).distinct()`, paginated 10 per page via Django's `Paginator`.

Only published posts are searchable; draft/in-review/unapproved content never appears in results regardless of who's searching.

## Validation / logging

- An empty query renders the page with no results (not an error) and logs the empty submission.
- Search terms containing SQL-injection-style keywords (`drop`, `delete`, `union`, `sql`, `--`, `;`) trigger a **security log entry only** (`logs/security.log`) — this is purely observational logging, not a WAF or input filter; the query itself is always safely parameterized through the Django ORM regardless of these terms, so this has no effect on search results.

## Robots

`{% block robots %}noindex, follow{% endblock %}` — search result pages are excluded from search-engine indexing but their outbound links are still followed.
