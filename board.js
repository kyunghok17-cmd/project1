// LocalStorage keys
const POSTS_KEY = 'board_posts';
const COMMENTS_KEY = 'board_comments';

// State
let posts = [];
let comments = [];
let currentPostId = null;
let currentPage = 1;
const postsPerPage = 10;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadData();
    showList();
});

// Load data from localStorage
function loadData() {
    const savedPosts = localStorage.getItem(POSTS_KEY);
    const savedComments = localStorage.getItem(COMMENTS_KEY);

    posts = savedPosts ? JSON.parse(savedPosts) : [];
    comments = savedComments ? JSON.parse(savedComments) : [];

    // Add sample data if empty
    if (posts.length === 0) {
        posts = [
            {
                id: Date.now(),
                title: '게시판에 오신 것을 환영합니다',
                content: '이곳은 자유롭게 글을 작성하고 공유할 수 있는 공간입니다.\n\n글쓰기 버튼을 눌러 새로운 글을 작성해보세요!',
                author: '관리자',
                date: new Date().toISOString(),
                views: 0
            }
        ];
        savePosts();
    }
}

// Save data to localStorage
function savePosts() {
    localStorage.setItem(POSTS_KEY, JSON.stringify(posts));
}

function saveComments() {
    localStorage.setItem(COMMENTS_KEY, JSON.stringify(comments));
}

// Show list view
function showList() {
    document.getElementById('boardList').style.display = 'block';
    document.getElementById('writeForm').style.display = 'none';
    document.getElementById('postDetail').style.display = 'none';

    renderPosts();
}

// Show write form
function showWriteForm() {
    document.getElementById('boardList').style.display = 'none';
    document.getElementById('writeForm').style.display = 'block';
    document.getElementById('postDetail').style.display = 'none';

    document.getElementById('formTitle').textContent = '글쓰기';
    document.getElementById('postForm').reset();
    document.getElementById('postId').value = '';
}

// Cancel write
function cancelWrite() {
    showList();
}

// Save post
function savePost(event) {
    event.preventDefault();

    const id = document.getElementById('postId').value;
    const title = document.getElementById('postTitle').value.trim();
    const content = document.getElementById('postContent').value.trim();
    const author = document.getElementById('postAuthor').value.trim();

    if (!title || !content || !author) {
        alert('모든 필드를 입력해주세요.');
        return;
    }

    if (id) {
        // Edit existing post
        const post = posts.find(p => p.id === parseInt(id));
        if (post) {
            post.title = title;
            post.content = content;
            post.author = author;
        }
    } else {
        // Create new post
        const newPost = {
            id: Date.now(),
            title,
            content,
            author,
            date: new Date().toISOString(),
            views: 0
        };
        posts.unshift(newPost);
    }

    savePosts();
    showList();
}

// Render posts
function renderPosts(filteredPosts = null) {
    const postsToRender = filteredPosts || posts;
    const postsList = document.getElementById('postsList');

    if (postsToRender.length === 0) {
        postsList.innerHTML = `
            <div class="empty-state">
                <h3>게시글이 없습니다</h3>
                <p>첫 번째 글을 작성해보세요!</p>
            </div>
        `;
        document.getElementById('pagination').innerHTML = '';
        return;
    }

    // Pagination
    const totalPages = Math.ceil(postsToRender.length / postsPerPage);
    const startIndex = (currentPage - 1) * postsPerPage;
    const endIndex = startIndex + postsPerPage;
    const currentPosts = postsToRender.slice(startIndex, endIndex);

    postsList.innerHTML = currentPosts.map(post => {
        const postComments = comments.filter(c => c.postId === post.id);
        const commentCount = postComments.length;
        const date = new Date(post.date);
        const formattedDate = `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')}`;

        return `
            <div class="post-item" onclick="viewPost(${post.id})">
                <div class="post-item-header">
                    <div>
                        <h3 class="post-item-title">${escapeHtml(post.title)} ${commentCount > 0 ? `<span class="comment-badge">[${commentCount}]</span>` : ''}</h3>
                        <div class="post-item-content">${escapeHtml(post.content)}</div>
                    </div>
                </div>
                <div class="post-item-meta">
                    <span>👤 ${escapeHtml(post.author)}</span>
                    <span>📅 ${formattedDate}</span>
                    <span>👁️ ${post.views}</span>
                </div>
            </div>
        `;
    }).join('');

    renderPagination(totalPages);
}

// Render pagination
function renderPagination(totalPages) {
    const pagination = document.getElementById('pagination');

    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }

    let html = '';

    // Previous button
    html += `<button onclick="changePage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>이전</button>`;

    // Page numbers
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
            html += `<button onclick="changePage(${i})" class="${i === currentPage ? 'active' : ''}">${i}</button>`;
        } else if (i === currentPage - 3 || i === currentPage + 3) {
            html += `<button disabled>...</button>`;
        }
    }

    // Next button
    html += `<button onclick="changePage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>다음</button>`;

    pagination.innerHTML = html;
}

// Change page
function changePage(page) {
    currentPage = page;
    renderPosts();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Search posts
function searchPosts() {
    const searchTerm = document.getElementById('searchInput').value.trim().toLowerCase();

    if (!searchTerm) {
        renderPosts();
        return;
    }

    const filteredPosts = posts.filter(post =>
        post.title.toLowerCase().includes(searchTerm) ||
        post.content.toLowerCase().includes(searchTerm) ||
        post.author.toLowerCase().includes(searchTerm)
    );

    currentPage = 1;
    renderPosts(filteredPosts);
}

// View post
function viewPost(postId) {
    currentPostId = postId;
    const post = posts.find(p => p.id === postId);

    if (!post) {
        alert('게시글을 찾을 수 없습니다.');
        return;
    }

    // Increment views
    post.views++;
    savePosts();

    document.getElementById('boardList').style.display = 'none';
    document.getElementById('writeForm').style.display = 'none';
    document.getElementById('postDetail').style.display = 'block';

    const date = new Date(post.date);
    const formattedDate = `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;

    document.getElementById('detailTitle').textContent = post.title;
    document.getElementById('detailAuthor').textContent = `작성자: ${post.author}`;
    document.getElementById('detailDate').textContent = `작성일: ${formattedDate}`;
    document.getElementById('detailViews').textContent = `조회수: ${post.views}`;
    document.getElementById('detailContent').textContent = post.content;

    renderComments(postId);

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Edit post
function editPost() {
    const post = posts.find(p => p.id === currentPostId);

    if (!post) {
        alert('게시글을 찾을 수 없습니다.');
        return;
    }

    document.getElementById('boardList').style.display = 'none';
    document.getElementById('writeForm').style.display = 'block';
    document.getElementById('postDetail').style.display = 'none';

    document.getElementById('formTitle').textContent = '글 수정';
    document.getElementById('postId').value = post.id;
    document.getElementById('postTitle').value = post.title;
    document.getElementById('postContent').value = post.content;
    document.getElementById('postAuthor').value = post.author;
}

// Delete post
function deletePost() {
    if (!confirm('정말로 이 게시글을 삭제하시겠습니까?')) {
        return;
    }

    posts = posts.filter(p => p.id !== currentPostId);
    comments = comments.filter(c => c.postId !== currentPostId);

    savePosts();
    saveComments();

    alert('게시글이 삭제되었습니다.');
    showList();
}

// Render comments
function renderComments(postId) {
    const postComments = comments.filter(c => c.postId === postId).sort((a, b) => b.date - a.date);
    const commentsList = document.getElementById('commentsList');
    const commentCount = document.getElementById('commentCount');

    commentCount.textContent = postComments.length;

    if (postComments.length === 0) {
        commentsList.innerHTML = '<div class="empty-state"><p>첫 번째 댓글을 작성해보세요!</p></div>';
        return;
    }

    commentsList.innerHTML = postComments.map(comment => {
        const date = new Date(comment.date);
        const formattedDate = `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;

        return `
            <div class="comment-item">
                <div class="comment-header">
                    <span class="comment-author">${escapeHtml(comment.author)}</span>
                    <span class="comment-date">${formattedDate}</span>
                </div>
                <div class="comment-content">${escapeHtml(comment.content)}</div>
                <div class="comment-actions">
                    <button onclick="deleteComment(${comment.id})">삭제</button>
                </div>
            </div>
        `;
    }).join('');
}

// Add comment
function addComment(event) {
    event.preventDefault();

    const author = document.getElementById('commentAuthor').value.trim();
    const content = document.getElementById('commentContent').value.trim();

    if (!author || !content) {
        alert('이름과 댓글 내용을 입력해주세요.');
        return;
    }

    const newComment = {
        id: Date.now(),
        postId: currentPostId,
        author,
        content,
        date: Date.now()
    };

    comments.push(newComment);
    saveComments();

    document.getElementById('commentAuthor').value = '';
    document.getElementById('commentContent').value = '';

    renderComments(currentPostId);
}

// Delete comment
function deleteComment(commentId) {
    if (!confirm('댓글을 삭제하시겠습니까?')) {
        return;
    }

    comments = comments.filter(c => c.id !== commentId);
    saveComments();
    renderComments(currentPostId);
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Search on Enter key
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                searchPosts();
            }
        });
    }
});
