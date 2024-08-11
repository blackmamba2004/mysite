from django.shortcuts import get_object_or_404, render
from django.http.request import HttpRequest
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.db.models import Count
from django.contrib.postgres.search import SearchVector, SearchRank, SearchQuery
from taggit.models import Tag
# from django.views.generic import ListView
from .models import Post
from .forms import EmailPostForm, CommentForm, SearchForm


def post_list(request: HttpRequest, tag_slug=None):
    post_list = Post.published.all()

    tag = None

    if tag_slug:
        tag = get_object_or_404(Tag, slug=tag_slug)
        post_list = post_list.filter(tags__in=[tag])

    # Постраничная разбивка с 3 постами на страницу
    paginator = Paginator(post_list, 3)
    page_number = request.GET.get('page')
    try:
        posts = paginator.page(page_number)

    except PageNotAnInteger:
        posts = paginator.page(1)

    except EmptyPage:
        posts = paginator.page(paginator.num_pages)

    context = {'posts': posts, 'tag': tag}

    return render(request, 'blog/post/list.html', context)


def post_detail(request: HttpRequest, year, month, day, slug):
    post = get_object_or_404(Post, status=Post.Status.PUBLISHED,
                                   publish__year=year, publish__month=month,
                                   publish__day=day, slug=slug)

    # Список активных комментариев к этому посту
    comments = post.comments.filter(active=True)

    # Форма для комментариев пользователей
    form = CommentForm()
    post_tags_ids = post.tags.values_list('id', flat=True)
    similar_posts = Post.published.filter(tags__in=post_tags_ids).exclude(id=post.id)
    similar_posts = similar_posts.annotate(same_tags=Count('tags')).order_by('-same_tags', '-publish')[:4]
    context = {'post': post, 'comments': comments, 'form': form, 'similar_posts': similar_posts}

    return render(request, 'blog/post/detail.html', context)


def post_share(request: HttpRequest, post_id):

    post = get_object_or_404(Post, id=post_id, status=Post.Status.PUBLISHED)

    sent = False

    if request.method == 'POST':
        form = EmailPostForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            post_url = request.build_absolute_uri(post.get_absolute_url())
            subject = f"{cd['name']} recommends you read {post.title}"
            message = f"Read {post.title} at {post_url}\n\n{cd['name']}\'s comments: {cd['comments']}"
            sent = True
            send_mail(subject, message, 'vasilsemen04@gmail.com', [cd['to']])
    else:
        form = EmailPostForm()

    return render(request, 'blog/post/share.html', {'post': post, 'form': form, 'sent': sent})


@require_POST
def post_comment(request: HttpRequest, post_id):
    post = get_object_or_404(Post, id=post_id, status=Post.Status.PUBLISHED)

    comment = None
    form = CommentForm(data=request.POST)
    if form.is_valid():
        comment = form.save(commit=False)

        comment.post = post

        comment.save()

    context = {
        'post': post, 
        'form': form, 
        'comment': comment
    }

    return render(request, 'blog/post/comment.html', context)


def post_search(request: HttpRequest):
    form = SearchForm()
    query = None
    results = []

    if 'query' in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data['query']
            search_vector = SearchVector('title', 'body')
            search_query = SearchQuery(query)
            results = Post.published.annotate(
                search = search_vector,
                rank = SearchRank(search_vector, search_query)
            ).filter(search=search_query).order_by('-rank')

    return render(request, 'blog/post/search.html', context={'form': form, 'query': query, 'results': results})
