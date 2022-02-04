import $ from 'jquery'
import Typeahead from 'typeahead.js'
import HEPDATA from './hepdata_common.js'

HEPDATA.initialise_user_filter = function () {

  const user_filter_field = $('#admin-user-filter');

  // Only go ahead if user is admin, i.e. that field exists
  if (user_filter_field.length == 0) {
    return;
  }

  // Simple matcher for typeahead filter
  var substringMatcher = function(data) {
    return function findMatches(query, callback) {
      var matches = [];
      $.each(data, function(i, datum) {
        if (datum.email.toLowerCase().indexOf(query.toLowerCase()) >= 0) {
          matches.push(datum);
        }
      });
      callback(matches);
    }
  }

  var users_url = '/dashboard/list-all-users'
  if (window.location.href.includes('/dashboard/submissions')) {
    users_url += '?coordinators_only=true'
  }
  $.get(users_url).done(function (data) {

    user_filter_field.typeahead(
      { highlight: true },
      {
        source: substringMatcher(data),
        templates: {
          suggestion: function(result) {
            return $('<p>').attr('id',result.id).text(result.email)[0].outerHTML;
          }
        }
      }
    );

    user_filter_field.bind('typeahead:select', function (event, suggestion) {
      $(this).typeahead('val', suggestion.email);
      const url = new URL(window.location.href);
      url.search = "view_as_user=" + suggestion.id;
      window.location.href = url.toString();
    });

    user_filter_field.attr(
      'placeholder',
      'Search users by email address'
    );

    user_filter_field.after(
      $("<i>").attr("class", "fa fa-times-circle").click(function() {
        user_filter_field.typeahead('val', '');
      })
    );

  });
};
