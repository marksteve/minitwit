(function($) {

	// UPDATE

	function updateMinitwits(latest) {
		var $mt = $('#minitwits');
		$.each(latest, function(i, post) {
			var postId = '#post_'+post.id;
			// Update dates of existing posts
			if ($(postId).size() == 1) {
				$('.date', postId).html(post.date);
			// Prepend post into list
			} else {
				$mt.prepend(
					$('<li></li>')
						.append($('<h3></h3>').html(post.username))
						.append($('<p></p>').html(post.text))
						.append($('<span></span>').html(post.date).addClass('date'))
						.attr('id', 'post_'+post.id)
						.fadeIn()
				);
			}
		});
		// Trim off excess posts
		var $posts = $('li', $mt);
		if ($posts.size() > 9) {
			$posts.slice(10, $posts.length).remove();
		}
	}

	// FORMS

	$('#postbox_form').submit(function() {
		var $f = $(this);
		$.ajax({
			type: 'put', // RESTful!
			url: '/post',
			data: $f.serialize(),
			dataType: 'json',
			success: function(data) {
				$('#postbox').val('');
				updateMinitwits(data);
			}
		})
		return false;
	});

	// POLLING
	
	if ($('#minitwits').size() > 0) {
		var poll, pollT, pollI = 1000;
		(poll = function(i) {
			clearTimeout(pollT);
			if (i > 10000) {
				i = 10000;
			}
			$.ajax({
				type: 'get', // RESTful!
				url: '/post',
				dataType: 'json',
				success: function(data) {
					updateMinitwits(data);
					pollT = setTimeout(function() {poll(i*1.1)}, i); // Increments by 10%
				}
			});
		})(pollI);
		$('#minitwits').mouseover(function() { // Resets on mousemove
			poll(pollI);
		});
	}

})($);