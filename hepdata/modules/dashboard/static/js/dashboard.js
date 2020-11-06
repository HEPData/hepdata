var dashboard = (function () {
  var data = {};

  var initialise_finalise_btn = function () {
    $(".finalise-btn").bind("click", function () {
      $("#finalise_submission_button").attr('data-recid', $(this).attr('data-recid'));
      $("#finalise_submission_button").attr('data-versions', $(this).attr('data-versions'));
      if ($(this).attr('data-versions') == 1) {
        $("#revision_commit_message").addClass("hidden");
      }
      $("#finaliseDialog").modal();
    });
  };

  var load_watched_records = function () {
    $.get('/subscriptions/list').done(function (data) {

      if (data.length > 0) {
        d3.select("#watch_container").html("");
      }


      var watch_list = d3.select("#watch_container").append("div").attr("class", "container-fluid watch-list");
      var watch_item = watch_list.selectAll("div.row").data(data).enter()
        .append("div")
        .attr("class", "row item")
        .attr("id", function (d) {
          return 'rec' + d.recid;
        });

      var watch_item_info = watch_item.append("div").attr("class", "col-md-11");

      watch_item_info.append("h4").attr("class", "title").append("a").attr("href", function (d) {
        return "/record/ins" + d.inspire_id;
      }).text(function (d) {
        return d.title;
      });

      watch_item_info.append("p").attr("class", "journal-info").text(function (d) {
        return d.journal_info;
      });

      watch_item_info.append("p").attr("class", "updated").text(function (d) {
        return "Last updated: " + d.last_updated;
      });

      var controls = watch_item.append("div").attr("class", "col-md-1 controls");
      controls.append("button").attr("class", "btn btn-sm btn-danger")
        .attr("onclick", function (d) {
          return "dashboard.unwatch('" + d.recid + "')";
        })
        .append("i").attr("class", "fa fa-eye-slash")
        .attr("title", "Unwatch Record")
        .attr("alt", "Unwatch Record");

    })
  };

  var generate_permissions_paginator = function(pagination_list, current_page, total_results, items_per_page) {
    var total_pages = Math.ceil(total_results / items_per_page);
    var pages_to_show = Array(
      {
        'enabled': (current_page > 1),
        'text': '«',
        'page': 1,
        'title': 'first'
      },
      {
        'enabled': (current_page > 1),
        'text': '‹',
        'page': (current_page > 1) ? current_page - 1 : 1,
        'title': 'prev'
      }
    );

    if (current_page > 1) {
      pages_to_show.push(
        {
          'enabled': true,
          'text': current_page - 1,
          'page': current_page - 1
        }
      );
    }

    pages_to_show.push(
      {
        'text': current_page,
        'page': current_page,
        'active': true,
        'enabled': false
      }
    );

    if (current_page < total_pages) {
      pages_to_show.push(
        {
          'enabled': true,
          'text': current_page + 1,
          'page': current_page + 1
        }
      );
    }

    pages_to_show.push(
      {
        'enabled': (current_page < total_pages),
        'text': '›',
        'page': (current_page < total_pages) ? current_page + 1 : total_pages,
        'title': 'next'
      },
      {
        'enabled': (current_page < total_pages),
        'text': '»',
        'page': total_pages,
        'title': 'last'
      }
    );

    pagination_list.selectAll("li").remove();
    pagination_list.selectAll("li")
      .data(pages_to_show).enter()
      .append("li").attr("class", function (d) {
        return d.active ? 'active' : (d.enabled ? '' : 'disabled');
      })
      .append("a").attr("href", '#')
      .attr("title", function (d) {
        return d.title;
      })
      .text(function (d) {
        return d.text;
      })
      .on('click', function (d) {
        event.preventDefault();
        return update_pagination(this, d.page, total_results, items_per_page);
      });
  }

  var update_pagination = function(current_element, page, total_results, items_per_page) {
    paginator = d3.select(current_element.parentElement.parentElement);
    generate_permissions_paginator(paginator, page, total_results, items_per_page);
    first_item = (page - 1) * items_per_page;

    d3.select(paginator.node().parentElement.parentElement).selectAll(".row").each(function(data, i) {
      if (i < first_item || i >= first_item + items_per_page) {
        $(this).hide();
      } else {
        $(this).show();
      }
    });
  }

  var load_permissions = function () {
    d3.select("#permissions").append("div").attr("align", "center").attr('id', 'permissions_loader');
    display_loader('#permissions_loader');

    $.get('/permissions/list').done(function (data) {

      d3.select("#permissions").html("");
      var _keys = ['coordinator', 'uploader', 'reviewer'];

      var _has_items = false;

      _keys.forEach(function (key) {
        if (data[key].length > 0) {
          _has_items = true;
        }
      });

      if(!_has_items) {

        d3.select("#permissions").append("div").attr("class", "alert alert-warning")
          .html("<strong>No contributions to show</strong>. " +
            "When you are a coordinator, uploader, or reviewer " +
            "for HEPData and contribute to a submission, you will see these here.");
        return;
      }

      var tabs = d3.select("#permissions").append("ul").attr("class", "nav nav-tabs").attr("role", "tab-list");

      var tab_content = d3.select("#permissions").attr("class", "tab-content");

      _keys.forEach(function (key, i) {

          // <li role="presentation" class="active"><a href="#home" aria-controls="home" role="tab" data-toggle="tab">Home</a></li>
          tabs.append("li").attr("role", "presentation").attr("class", i == 0 ? "active" : "").append("a").attr("href", "#" + key)
            .attr("aria-controls", key).attr("class", "tab-list-nav-item").attr("role", "tab").attr("data-toggle", "tab").text(key);

          // <div role="tabpanel" class="tab-pane fade in active" id="home">...</div>
          var permission_list = tab_content.append("div")
            .attr("class", "container-fluid permission-list tab-pane fade in " + (i == 0 ? "active" : ""))
            .attr("role", "tabpanel")
            .attr("id", key);

          var items_per_page = 5;

          // tab_content = '<div role="tabpanel" class="tab-pane active" id="home">...</div>'
          var permission_item = permission_list.selectAll("div.row").data(data[key]).enter()
            .append("div")
            .attr("class", "row item")
            .attr("style", function (d, i) {
              return i < items_per_page ? '' : 'display:none;';
            })
            .attr("id", function (d) {
              return 'rec' + d.recid;
            });

          var permission_item_info = permission_item.append("div").attr("class", "col-md-12");

          permission_item_info.append("h4").attr("class", "title").append("a").attr("href", function (d) {
            return "/record/" + d.recid;
          }).text(function (d) {
            return d.title;
          });

          permission_item_info.append("p").attr("class", "journal-info").text(function (d) {
            return d.journal_info;
          });

          permission_item_info.append("div").attr("class", "label label-info").text(function (d) {
            return key;
          });

          // Add paginator similar to theme/templates/pagination.html
          if (data[key].length > items_per_page) {
            var pagination_list = permission_list
              .append("div").attr("class", "pagination-bar").attr("align", "center")
              .append("ul").attr("class", "pagination");
            generate_permissions_paginator(pagination_list, 1, data[key].length, items_per_page);
          }
        }
      );

    });
  };

  var load_submissions_from_params = function(params) {
    var loader_placement = "#submissions-loader";

    // If there's already a submission list put the loader there (to keep the pagination)
    var submission_list = $('#hep-submissions');
    if (submission_list.length > 0) {
      submission_list.empty().addClass('loader').css('width', '200px');
      loader_placement = '#hep-submissions'
    }
    display_loader(loader_placement);

    var url = "/dashboard/dashboard-submissions?" + $.param(params);
    $.get(url).done(function (data) {
      $(loader_placement).hide();
      $('#submissions-wrapper').html(data).fadeIn(500);

      $(".inspire-btn").bind("click", function () {
        $("#inspire-add-button").attr('data-recid', $(this).attr("data-recid"));
        $("#inspireDialog").modal();
      });

      dashboard.render_submission_stats();

      $('.pagination li a').click(function(event) {
        event.preventDefault();
        load_submissions(this);
      });
    }).fail(function () {
      $(loader_placement).hide();
      $('#submissions-wrapper').html("Unable to load submissions. Please try again later.").fadeIn(500);
    });
  }

  var load_submissions = function(element) {
    var href = window.location.href;
    if (element && element.href) {
      href = element.href;
    }
    var url = new URL(href);
    var page = url.searchParams.get('page');
    if (!page) page = 1;

    load_submissions_from_params({'page': page});
  };

  var display_loader = function(placement) {
    $(placement).show();
    HEPDATA.render_loader(
      placement,
      [
        {x: 26, y: 30, color: "#955BA5"},
        {x: -60, y: 55, color: "#FFFFFF"},
        {x: 37, y: -10, color: "#955BA5"},
        {x: -60, y: 10, color: "#955BA5"},
        {x: -27, y: -30, color: "#955BA5"},
        {x: 60, y: -55, color: "#FFFFFF"}
      ],
      {"width": 200, "height": 200}
    );
  };

  var initialise_list_filter = function () {

    // Simple matcher for typeahead filter
    var substringMatcher = function(data) {
      return function findMatches(query, callback) {
        var matches = [];
        $.each(data, function(i, datum) {
          if (datum.title.toLowerCase().indexOf(query.toLowerCase()) >= 0) {
            matches.push(datum);
          }
        });
        callback(matches);
      }
    }

    $.get('/dashboard/dashboard-submission-titles').done(function (data) {

      $('#submission-filter').typeahead(
        { highlight: true },
        {
          source: substringMatcher(data),
          templates: {
            suggestion: function(result) {
              return $('<p>').attr('id',result.id).text(result.title)[0].outerHTML;
            }
          }
        }
      );

      $('#submission-filter').bind('typeahead:select', function (event, suggestion) {
        $(this).typeahead('val', suggestion.title);
        load_submissions_from_params({'record_id': suggestion.id});
      });

      $('#submission-filter').attr(
        'placeholder',
        "Filter " + data.length + " submission" + (data.length > 1 ? 's' : '')
      );

      $('#submission-filter').after(
        $("<i>").attr("class", "fa fa-times-circle").click(function() {
          $('#submission-filter').typeahead('val', '');
          load_submissions_from_params({});
        })
      );

    });
  };

  return {
    initialise: function () {
      MathJax.Hub.Config({
        tex2jax: {inlineMath: [['$', '$'], ['\\(', '\\)']]}
      });

      MathJax.Hub.Queue(["Typeset", MathJax.Hub]);

      initialise_list_filter();
      initialise_finalise_btn();
      load_submissions();
      load_watched_records();
      load_permissions();

      $(".reindex-btn").bind("click", function () {
        $("#reindexDialog").modal();
      });
    },

    unwatch: function (recid) {
      var url = "/subscriptions/unsubscribe/" + recid;
      $.post(url).done(function (data) {
        $("#rec" + recid).remove();
      }).fail(function (data) {
        alert("Unable to unwatch this record. An error occurred.");
      })
    },

    render_submission_stats: function () {
      for (var submission_idx in this.data) {
        HEPDATA.visualization.submission_status.render(this.data[submission_idx]);
      }
    }
  }
})();
