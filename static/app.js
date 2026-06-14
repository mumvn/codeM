const categories = ['platform', 'orchestration', 'end-user'];
const syncButton = document.getElementById('syncButton');
const syncStatus = document.getElementById('syncStatus');
const errorBanner = document.getElementById('errorBanner');

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Date unavailable';
  return new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC',
  }).format(date).toUpperCase();
}

function emptyState(category) {
  const empty = document.createElement('div');
  empty.className = 'empty-state';
  empty.innerHTML = '<span>◇</span><strong>No briefs cached yet</strong><p>Sync the curated feeds to build this architecture layer.</p>';
  document.getElementById(`${category}-list`).appendChild(empty);
}

function renderArticles(articles) {
  categories.forEach((category) => {
    const list = document.getElementById(`${category}-list`);
    list.replaceChildren();
    const matches = articles.filter((article) => article.category === category);
    document.getElementById(`${category}-count`).textContent = `${matches.length} ${matches.length === 1 ? 'BRIEF' : 'BRIEFS'}`;

    matches.forEach((article) => {
      const card = document.getElementById('articleTemplate').content.cloneNode(true);
      const links = card.querySelectorAll('a');
      links.forEach((link) => { link.href = article.link; });
      card.querySelector('h3 a').textContent = article.title;
      const time = card.querySelector('time');
      time.dateTime = article.pub_date;
      time.textContent = formatDate(article.pub_date);
      card.querySelector('.summary p').textContent = article.ai_summary || 'Summary pending.';
      list.appendChild(card);
    });
    if (!matches.length) emptyState(category);
  });
  document.getElementById('articleCount').textContent = articles.length;
}

async function loadArticles() {
  const response = await fetch('/api/articles', { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error('Unable to load the architecture digest.');
  const articles = await response.json();
  renderArticles(articles);
  return articles;
}

async function synchronize() {
  syncButton.disabled = true;
  syncButton.classList.add('syncing');
  syncStatus.textContent = 'Synchronizing curated sources…';
  errorBanner.hidden = true;
  try {
    const response = await fetch('/api/sync', {
      method: 'POST',
      headers: { Accept: 'application/json' },
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Feed synchronization failed.');
    await loadArticles();
    const failures = result.feeds.reduce((total, feed) => total + feed.errors.length, 0);
    syncStatus.textContent = `${result.added} added · ${result.skipped} already current`;
    if (failures) {
      errorBanner.textContent = `Synchronization completed with ${failures} item-level warning${failures === 1 ? '' : 's'}.`;
      errorBanner.hidden = false;
    }
  } catch (error) {
    syncStatus.textContent = 'Synchronization unavailable';
    errorBanner.textContent = error.message;
    errorBanner.hidden = false;
  } finally {
    syncButton.disabled = false;
    syncButton.classList.remove('syncing');
  }
}

syncButton.addEventListener('click', synchronize);
loadArticles().catch((error) => {
  errorBanner.textContent = error.message;
  errorBanner.hidden = false;
  categories.forEach(emptyState);
});
