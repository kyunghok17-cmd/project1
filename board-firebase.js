// Firebase Board with Firestore
import { db } from './firebase-config.js';
import {
    collection,
    addDoc,
    getDocs,
    getDoc,
    doc,
    updateDoc,
    deleteDoc,
    query,
    orderBy,
    serverTimestamp,
    onSnapshot
} from "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";

// Collections
const postsCollection = collection(db, 'posts');
const commentsCollection = collection(db, 'comments');

// State
let posts = [];
let comments = [];
let currentPostId = null;
let currentPage = 1;
const postsPerPage = 10;
let unsubscribePosts = null;
let unsubscribeComments = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadPosts();
    showList();
});

// Load posts from Firestore with real-time updates
async function loadPosts() {
    const q = query(postsCollection, orderBy('createdAt', 'desc'));

    unsubscribePosts = onSnapshot(q, (snapshot) => {
        posts = [];
        snapshot.forEach((doc) => {
            posts.push({
                id: doc.id,
                ...doc.data()
            });
        });

        // If we're on the list view, refresh it
        if (document.getElementById('boardList').style.display !== 'none') {
            renderPosts();
        }
    });
}

// Show list view
function showList() {
    document.getElementById('boardList').style.display = 'block';
    document.getElementById('writeForm').style.display = 'none';
    document.getElementById('postDetail').style.display = 'none';

    renderPosts();
}
window.showList = showList;

// Show write form
function showWriteForm() {
    document.getElementById('boardList').style.display = 'none';
    document.getElementById('writeForm').style.display = 'block';
    document.getElementById('postDetail').style.display = 'none';

    document.getElementById('formTitle').textContent = '글쓰기';
    document.getElementById('postForm').reset();
    document.getElementById('postId').value = '';
}
window.showWriteForm = showWriteForm;

// Cancel write
function cancelWrite() {
    showList();
}
window.cancelWrite = cancelWrite;

// Save post
async function savePost(event) {
    event.preventDefault();

    const id = document.getElementById('postId').value;
    const title = document.getElementById('postTitle').value.trim();
    const content = document.getElementById('postContent').value.trim();
    const author = document.getElementById('postAuthor').value.trim();

    if (!title || !content || !author) {
        alert('모든 필드를 입력해주세요.');
        return;
    }

    try {
        if (id) {
            // Edit existing post
            const postRef = doc(db, 'posts', id);
            await updateDoc(postRef, {
                title,
                content,
                author,
                updatedAt: serverTimestamp()
            });
            alert('게시글이 수정되었습니다.');
        } else {
            // Create new post
            await addDoc(postsCollection, {
                title,
                content,
                author,
                views: 0,
                createdAt: serverTimestamp(),
                updatedAt: serverTimestamp()
            });
            alert('게시글이 작성되었습니다.');
        }
        showList();
    } catch (error) {
        console.error('Error saving post:', error);
        alert('게시글 저장 중 오류가 발생했습니다.');
    }
}
window.savePost = savePost;

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

        let formattedDate = '날짜 없음';
        if (post.createdAt) {
            const date = post.createdAt.toDate ? post.createdAt.toDate() : new Date(post.createdAt);
            formattedDate = `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')}`;
        }

        return `
            <div class="post-item" onclick="viewPost('${post.id}')">
                <div class="post-item-header">
                    <div>
                        <h3 class="post-item-title">${escapeHtml(post.title)} ${commentCount > 0 ? `<span class="comment-badge">[${commentCount}]</span>` : ''}</h3>
                        <div class="post-item-content">${escapeHtml(post.content)}</div>
                    </div>
                </div>
                <div class="post-item-meta">
                    <span>👤 ${escapeHtml(post.author)}</span>
                    <span>📅 ${formattedDate}</span>
                    <span>👁️ ${post.views || 0}</span>
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
    html += `<button onclick="changePage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>이전</button>`;

    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
            html += `<button onclick="changePage(${i})" class="${i === currentPage ? 'active' : ''}">${i}</button>`;
        } else if (i === currentPage - 3 || i === currentPage + 3) {
            html += `<button disabled>...</button>`;
        }
    }

    html += `<button onclick="changePage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>다음</button>`;
    pagination.innerHTML = html;
}

// Change page
function changePage(page) {
    currentPage = page;
    renderPosts();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}
window.changePage = changePage;

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
window.searchPosts = searchPosts;

// View post
async function viewPost(postId) {
    currentPostId = postId;

    try {
        const postRef = doc(db, 'posts', postId);
        const postSnap = await getDoc(postRef);

        if (!postSnap.exists()) {
            alert('게시글을 찾을 수 없습니다.');
            return;
        }

        const post = { id: postSnap.id, ...postSnap.data() };

        // Increment views
        await updateDoc(postRef, {
            views: (post.views || 0) + 1
        });

        document.getElementById('boardList').style.display = 'none';
        document.getElementById('writeForm').style.display = 'none';
        document.getElementById('postDetail').style.display = 'block';

        let formattedDate = '날짜 없음';
        if (post.createdAt) {
            const date = post.createdAt.toDate ? post.createdAt.toDate() : new Date(post.createdAt);
            formattedDate = `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
        }

        document.getElementById('detailTitle').textContent = post.title;
        document.getElementById('detailAuthor').textContent = `작성자: ${post.author}`;
        document.getElementById('detailDate').textContent = `작성일: ${formattedDate}`;
        document.getElementById('detailViews').textContent = `조회수: ${(post.views || 0) + 1}`;
        document.getElementById('detailContent').textContent = post.content;

        loadComments(postId);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (error) {
        console.error('Error viewing post:', error);
        alert('게시글을 불러오는 중 오류가 발생했습니다.');
    }
}
window.viewPost = viewPost;

// Edit post
async function editPost() {
    try {
        const postRef = doc(db, 'posts', currentPostId);
        const postSnap = await getDoc(postRef);

        if (!postSnap.exists()) {
            alert('게시글을 찾을 수 없습니다.');
            return;
        }

        const post = { id: postSnap.id, ...postSnap.data() };

        document.getElementById('boardList').style.display = 'none';
        document.getElementById('writeForm').style.display = 'block';
        document.getElementById('postDetail').style.display = 'none';

        document.getElementById('formTitle').textContent = '글 수정';
        document.getElementById('postId').value = post.id;
        document.getElementById('postTitle').value = post.title;
        document.getElementById('postContent').value = post.content;
        document.getElementById('postAuthor').value = post.author;
    } catch (error) {
        console.error('Error loading post for edit:', error);
        alert('게시글을 불러오는 중 오류가 발생했습니다.');
    }
}
window.editPost = editPost;

// Delete post
async function deletePost() {
    if (!confirm('정말로 이 게시글을 삭제하시겠습니까?')) {
        return;
    }

    try {
        // Delete post
        await deleteDoc(doc(db, 'posts', currentPostId));

        // Delete all comments for this post
        const q = query(commentsCollection);
        const snapshot = await getDocs(q);
        const deletePromises = [];

        snapshot.forEach((docSnap) => {
            const comment = docSnap.data();
            if (comment.postId === currentPostId) {
                deletePromises.push(deleteDoc(doc(db, 'comments', docSnap.id)));
            }
        });

        await Promise.all(deletePromises);

        alert('게시글이 삭제되었습니다.');
        showList();
    } catch (error) {
        console.error('Error deleting post:', error);
        alert('게시글 삭제 중 오류가 발생했습니다.');
    }
}
window.deletePost = deletePost;

// Load comments with real-time updates
function loadComments(postId) {
    if (unsubscribeComments) {
        unsubscribeComments();
    }

    const q = query(commentsCollection, orderBy('createdAt', 'desc'));

    unsubscribeComments = onSnapshot(q, (snapshot) => {
        comments = [];
        snapshot.forEach((doc) => {
            const data = doc.data();
            if (data.postId === postId) {
                comments.push({
                    id: doc.id,
                    ...data
                });
            }
        });
        renderComments();
    });
}

// Render comments
function renderComments() {
    const commentsList = document.getElementById('commentsList');
    const commentCount = document.getElementById('commentCount');

    commentCount.textContent = comments.length;

    if (comments.length === 0) {
        commentsList.innerHTML = '<div class="empty-state"><p>첫 번째 댓글을 작성해보세요!</p></div>';
        return;
    }

    commentsList.innerHTML = comments.map(comment => {
        let formattedDate = '날짜 없음';
        if (comment.createdAt) {
            const date = comment.createdAt.toDate ? comment.createdAt.toDate() : new Date(comment.createdAt);
            formattedDate = `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
        }

        return `
            <div class="comment-item">
                <div class="comment-header">
                    <span class="comment-author">${escapeHtml(comment.author)}</span>
                    <span class="comment-date">${formattedDate}</span>
                </div>
                <div class="comment-content">${escapeHtml(comment.content)}</div>
                <div class="comment-actions">
                    <button onclick="deleteComment('${comment.id}')">삭제</button>
                </div>
            </div>
        `;
    }).join('');
}

// Add comment
async function addComment(event) {
    event.preventDefault();

    const author = document.getElementById('commentAuthor').value.trim();
    const content = document.getElementById('commentContent').value.trim();

    if (!author || !content) {
        alert('이름과 댓글 내용을 입력해주세요.');
        return;
    }

    try {
        await addDoc(commentsCollection, {
            postId: currentPostId,
            author,
            content,
            createdAt: serverTimestamp()
        });

        document.getElementById('commentAuthor').value = '';
        document.getElementById('commentContent').value = '';
    } catch (error) {
        console.error('Error adding comment:', error);
        alert('댓글 작성 중 오류가 발생했습니다.');
    }
}
window.addComment = addComment;

// Delete comment
async function deleteComment(commentId) {
    if (!confirm('댓글을 삭제하시겠습니까?')) {
        return;
    }

    try {
        await deleteDoc(doc(db, 'comments', commentId));
    } catch (error) {
        console.error('Error deleting comment:', error);
        alert('댓글 삭제 중 오류가 발생했습니다.');
    }
}
window.deleteComment = deleteComment;

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Search on Enter
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
