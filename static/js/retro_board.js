/**
 * Retrospective Board Drag-and-Drop Card Clustering using SortableJS.
 */
document.addEventListener('DOMContentLoaded', () => {
    initRetroSortables();
});

// Support dynamic elements added via HTMX
document.addEventListener('htmx:afterSwap', () => {
    initRetroSortables();
});

function getCsrfToken() {
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input) return input.value;
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
}

function showToast(message, type = 'error') {
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'fixed bottom-5 right-5 z-50 flex flex-col gap-2 max-w-sm';
        document.body.appendChild(toastContainer);
    }

    const toast = document.createElement('div');
    const bgColor = type === 'error' ? 'bg-rose-600 text-white' : 'bg-slate-800 text-white';
    toast.className = `${bgColor} px-4 py-3 rounded-xl shadow-lg text-xs font-semibold flex items-center justify-between gap-3 transition transform duration-200 ease-out`;
    toast.innerHTML = `
        <span>${message}</span>
        <button class="text-white/80 hover:text-white font-bold">&times;</button>
    `;

    toast.querySelector('button').addEventListener('click', () => toast.remove());
    toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function updateCardCounts() {
    // Update unclustered count
    const unclusteredList = document.getElementById('unclustered-cards-list');
    const unclusteredCount = document.getElementById('unclustered-count');
    if (unclusteredList && unclusteredCount) {
        const cards = unclusteredList.querySelectorAll('[data-card-id]');
        unclusteredCount.textContent = cards.length;
    }

    // Update all cluster counts
    document.querySelectorAll('.sortable-cards-pool[data-cluster-id]').forEach(pool => {
        const clusterId = pool.dataset.clusterId;
        if (!clusterId) return;
        const countBadge = document.querySelector(`#cluster-${clusterId} .cluster-count-badge`);
        if (countBadge) {
            const cards = pool.querySelectorAll('[data-card-id]');
            countBadge.textContent = `${cards.length} Card${cards.length === 1 ? '' : 's'}`;
        }
    });
}

function initRetroSortables() {
    if (typeof Sortable === 'undefined') {
        console.warn('SortableJS library is not loaded.');
        return;
    }

    const pools = document.querySelectorAll('.sortable-cards-pool');
    pools.forEach(pool => {
        if (pool._sortableInitialized) return;
        pool._sortableInitialized = true;

        new Sortable(pool, {
            group: 'retro-cards',
            animation: 150,
            ghostClass: 'opacity-40',
            chosenClass: 'scale-[1.02]',
            dragClass: 'shadow-xl',
            handle: '.card-drag-handle',
            draggable: '[data-card-id]',
            onEnd: function (evt) {
                const item = evt.item;
                const cardId = item.dataset.cardId;
                const fromContainer = evt.from;
                const toContainer = evt.to;

                // If position did not change, no-op
                if (fromContainer === toContainer && evt.oldIndex === evt.newIndex) {
                    return;
                }

                const targetClusterId = toContainer.dataset.clusterId || '';

                // Asynchronously persist card movement
                const formData = new FormData();
                formData.append('cluster_id', targetClusterId);

                fetch(`/retro/cards/${cardId}/move/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: formData
                })
                .then(async response => {
                    if (!response.ok) {
                        const errData = await response.json().catch(() => ({}));
                        throw new Error(errData.message || `Server returned HTTP ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    updateCardCounts();
                })
                .catch(err => {
                    console.error('Failed to persist card move:', err);
                    showToast('Failed to save card position. Reverting...', 'error');
                    // Revert DOM position
                    if (fromContainer) {
                        if (fromContainer.children[evt.oldIndex]) {
                            fromContainer.insertBefore(item, fromContainer.children[evt.oldIndex]);
                        } else {
                            fromContainer.appendChild(item);
                        }
                    }
                    updateCardCounts();
                });
            }
        });
    });
}
