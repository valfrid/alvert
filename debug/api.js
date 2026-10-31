var jQueryScriptOutputted = false;
function initJQuery() {
    //if the jQuery object isn't available
    if (typeof(jQuery) == 'undefined') {
        if (! jQueryScriptOutputted) {
            jQueryScriptOutputted = true;
            document.write('<scr' + 'ipt type="text/javascript" src="https://static.blogg.se/shared/js/jquery-1.9.1.min.js"></scr' + 'ipt>');
        }
        setTimeout("initJQuery()", 50);
    }       
}
initJQuery();

var loading = false;
var last_ts = 0;
var loadThreshold = 0.9;

function loadMoreContent(type, contentDiv, callback) {
	if(!loading) {
        if (type == "index") {
            moreEntries(contentDiv, last_ts, callback)
        } else if (type == "archive") {
            moreArchiveEntries(contentDiv, last_ts, callback)
        } else if (type == "category") {
            moreCategoryEntries(contentDiv, last_ts, callback)
        }
    }
}

function moreEntries(contentDiv, timestamp, callback) {
	contentLoader('/_more/entries_' + timestamp, contentDiv, callback);
}

function moreArchiveEntries(contentDiv, timestamp, callback) {
	if(match = document.location.pathname.match(/\/(20[0-9]{2})\/([a-z]+)\/[^\/]*$/)) {
		contentLoader('/_more/entries_'+ match[1] + '-'+ match[2] +'_' + timestamp, contentDiv, callback);
	}
}

function moreCategoryEntries(contentDiv, timestamp, callback) {
	if(match = document.location.pathname.match(/\/tag\/([a-z0-9_-]+)\.html$/)) {
		contentLoader('/_more/entries_tag_'+ match[1] +'_' + timestamp, contentDiv, callback);
	}
	else if(match = document.location.pathname.match(/\/([a-z0-9_-]+)\.html$/)) {
		contentLoader('/_more/entries_'+ match[1] +'_' + timestamp, contentDiv, callback);
	}
}

function moreComments(contentDiv,entry,timestamp, callback) {
	contentLoader('/_more/comments_' + entry + '_'+ timestamp, contentDiv, callback);
}

function loadMoreComments(entry, commentDiv, callback) {
	moreComments(contentDiv,"", last_comment_ts, callback)
}

var cancelXhr;
function contentLoader(url, div, callback) {
  if (cancelXhr) return;

	loading = true;
	match = document.location.pathname.match(/^(?!(?:\/category|\/tag|\/20[0-9][0-9]))(\/[^\/]+)\//i);
	if(match) {
		url = match[1] + url;
  }
  
	var xhr = $.getJSON(url).done(function(data) {
		// Remove any document.write() statements from ajax-fetched content, since it breaks everything otherwise...
		// data.entries_rendered = data.entries_rendered.replace(/document\.write\((.*?)\)/g, '');
		document.write = function() {}
		// div.append(data.entries_rendered);

    // InnerHTML doesn't execute inserted scripts - use jQuery append() instead
    // div.get(0).innerHTML += data.entries_rendered;
    $(div.get(0)).append(data.entries_rendered);

    try {
      window.loadAds()
    } catch (e) {
      console.warn('Missing window.loadAds function. Can\'t load more ads')
    }

		if(data.count) {
			loading=false;
			last_ts = data.last_ts
		} else {
			/* Reached the end, stop loading */
			loading = true
    }
		if(callback) {
			if (typeof(TipserWidget) == "object") {
				TipserWidget.ImageTagger.scanImages();
			}
			callback(data);
		}
		if (typeof(window.BSELikes) == "object") {
			window.BSELikes.more_entries();
		}
		if (typeof(window.BSEEmojis) == "object") {
			window.BSEEmojis.more_entries();
		}
	}).fail(function() {
    // If we fail, lets not block the loading in case user tries again
    loading=false;
  }).always(function () {
    clearTimeout(cancelXhr)
    cancelXhr = undefined
    // Remove the spinner
    $('.LoadMore-Spinner').remove()
  });

  // Set timeout for getJSON call.
  cancelXhr = setTimeout(function () {
    cancelXhr = undefined
    xhr.abort()
  }, 10000);
}

var _animFrameDoCheckLoadMore;
var _debounceDoCheckLoadMore;
function _doCheckLoadMore () {
  // Throttle animation frame
  if (!_animFrameDoCheckLoadMore) {
    _animFrameDoCheckLoadMore = requestAnimationFrame(_doCheckLoadMore.bind(this));
    return;
  }

  // Actual action
  // Setting a 10 pixel margin to avoid issues with rounding etc. example http://mincancanresa.blogg.se
  if  ((($(window).scrollTop() + window.innerHeight + 10) >= (this.contentDiv.offset().top + this.contentDiv.height())) && !_debounceDoCheckLoadMore){
    _debounceDoCheckLoadMore = true
    // TODO: Inject load more spinner...
    if ($(".LoadMore-Spinner").length <= 0) {
      var spinnerEl = $('<div class="LoadMore-Spinner"><svg width="40px" height="20px" viewBox="0 0 40 20" version="1.1" xmlns="http://www.w3.org/2000/svg"><circle id="spot_1" cx="5" cy="10" r="5"></circle><circle id="spot_2" cx="20" cy="10" r="5"></circle><circle id="spot_3" cx="35" cy="10" r="5"></circle></svg><style>@keyframes pulse {0% {r: 0;}33% {r: 5;}100% {r: 5;}}.LoadMore-Spinner #spot_1,.LoadMore-Spinner #spot_2,.LoadMore-Spinner #spot_3 {fill: #FFFFFF;animation-name: pulse;animation-duration: 1.5s;animation-iteration-count: infinite;}.LoadMore-Spinner #spot_1 {animation-delay: 0s;}.LoadMore-Spinner #spot_2 {animation-delay: 0.15s;}.LoadMore-Spinner #spot_3 {animation-delay: 0.3s;}</style></div>')
      spinnerEl.css({
        position: 'relative',
        width: '100%',
        'text-align': 'center',
        background: 'rgba(0,0,0,0.6)',
        padding: '10px',
        color: 'white',
        'align-items': 'center',
        'justify-content': 'center'
      })
      $(document.body).append(spinnerEl);
    }

    setTimeout(function () {
      _debounceDoCheckLoadMore = false;
      var callback = this.callback;
      loadMoreContent(this.type, this.contentDiv, this.callback);
      
      // Clear animation frame
      _animFrameDoCheckLoadMore = undefined
    }.bind(this), 300);
  } else {
    // Clear animation frame
    _animFrameDoCheckLoadMore = undefined;
  }
}

var _animFrameDoCheckOnResize
function _doCheckOnResize () {
  // Throttle animation frame
  if (!_animFrameDoCheckOnResize) {
    _animFrameDoCheckOnResize = requestAnimationFrame(_doCheckLoadMore.bind(this));
    return;
  }

  // Actual action
  iheight = window.innerHeight ? window.innerHeight : $(window).height();
	if(this.contentDiv.offset().top + this.contentDiv.height() < iheight) {
    loadMoreContent(this.type, this.contentDiv, this.callback);
  }
  
  // Clear animation frame
  _animFrameDoCheckOnResize = undefined
}


function bindContentLoader(type, contentDiv, timestamp, callback) {
	last_ts = timestamp;
  _doCheckOnResize.call({ type: type, contentDiv: contentDiv, timestamp: timestamp, callback: callback })
  
	$(window).scroll(_doCheckLoadMore.bind({ type: type, contentDiv: contentDiv, timestamp: timestamp, callback: callback }));
	$(window).resize(_doCheckOnResize.bind({ type: type, contentDiv: contentDiv, timestamp: timestamp, callback: callback }));
}

function bindClickLoader(clickDiv, type, contentDiv, timestamp, callback) {
	clickDiv.hide();
	bindContentLoader(type, contentDiv, timestamp, callback);
}

function bindCommentLoader(entry, contentDiv, timestamp, callback) {
	last_comment_ts = timestamp;
	return $(window).scroll(function(){
		iheight = window.innerHeight ? window.innerHeight : $(window).height();
		if  ($(window).scrollTop() >= ($(document).height() - iheight) * loadThreshold){
			loadMoreComments(entry, contentDiv, callback);
		}
	});
}


function showPic(srcImg) {
	$("body").append("<div id='background-cover'></div>");
	$("#background-cover").css({
		position: 'fixed', width: '100%', height: '100%', left: '0', top: '0',
		'background-color': 'rgba(0,0,0,0.85)', 'z-index': 15000
	})
	.append("<img src='"+srcImg+"' id='fullsize-image'> ");

	$("#fullsize-image").css({
		'max-width': '95%', 'max-height': '95%', margin: '0 auto', display: 'none', 
		border: '6px solid black', 'border-radius': '8px', position: 'absolute'
	})
	.load(function() {
		var w = $(this).width(), h = $(this).height(),
			screenw = $("#background-cover").width(), screenh = $("#background-cover").height();
		$("#fullsize-image").css({left: ((screenw-w)/2) + 'px', top: ((screenh-h)/2) + 'px'}).fadeIn('fast');
	});

	$("#background-cover").on('click', function(e) {
		$(this).remove();
	})
}



// OLD COMMENTS.JS 
var isChanged = 0,
	d = document.domain,
	domain = (d.split(".").length == 3) ? d.substring(d.indexOf('.')) : d;
function setCookie(name, value, expires){
    document.cookie = name + '=' + escape(value) + '; expires=' + expires.toGMTString() + '; domain=' + domain + '; path=/';
}

function getCookie(name){
    var key = name + '=';
    var c = document.cookie;
    var i = c.indexOf(key);
    if(i < 0) return '';
    var j = c.indexOf(';', i + key.length);
    if(j < 0) j = c.length;
    return unescape(c.substring(i + key.length, j));
}

function deleteCookie(name){
    if(getCookie(name))
        setCookie(name, '', new Date(70, 0, 1, 0, 0, 1));
}

function populateFormValues(frm){
    if(frm) {
		author = frm.author || {};
		email = frm.email ? frm.email : frm.authoremail;
		url = frm.url ? frm.url : frm.authorurl;
		url = url || {};
		email = email || {};

		author.value = getCookie("bdauthor");
		email.value = getCookie("bdemail");
		url.value = decodeURIComponent(getCookie("bdurl"));

		if(!author.value){
			url.value = 'http://';
		}
		if(author.value) {
			document.commentForm.remember.checked = 1;	
		}
	}
}

function unPopulateFormValues(frm){
    author = frm.author;
    email = frm.email ? frm.email : frm.authoremail;
    url = frm.url ? frm.url : frm.authorurl;
    author.value = '';
    email.value = '';
    url.value = 'http://';
}

function doSubmit(frm){
    if(frm.remember.checked) {
	    var now = new Date();
	    now.setTime(now.getTime() + 365 * 24 * 60 * 60 * 1000);
	    email = frm.email ? frm.email.value : frm.authoremail.value;
	    url = frm.url ? frm.url.value : frm.authorurl.value;
	    setCookie('bdauthor', frm.author.value, now);
	    setCookie('bdemail', email, now);
	    setCookie('bdurl', url, now);    	
    }
    else {
	    deleteCookie('bdauthor');
	    deleteCookie('bdemail');
	    deleteCookie('bdurl');
    }
}

function doCheck(e){
    if(isChanged) return;
    if(e.checked)
        populateFormValues(e.form);
    else
        unPopulateFormValues(e.form);
}

function doChange(e){
    isChanged = 1;
}

function waitForJquery() {
    if (window.$){
		$.fn.fitVids = function(){};
		$(document).ready(function() {
        $('a[href*="//profile.publishme.se/profile/view/"]').removeAttr("href").css('cursor','auto');
			  if(document.commentForm) {
			    populateFormValues(document.commentForm);
		    }
		});
    } else {
        setTimeout(waitForJquery, 50);
    }
}
setTimeout(waitForJquery, 50);


