var dashboard = (function () {
  var initialise_list_filter = function () {
    $(".filter-list li").bind('click', function () {
      var id_parts = this.id.split("-");
      var item_parent = id_parts[0];
      // we need to reset all of the items to unselected before selecting the new item.
      $("#" + item_parent + "-filter li").each(function () {
        $(this).removeClass("filter-selected");
        $(this).addClass("filter-inactive");
      });

      $(this).addClass("filter-selected");
      $(this).removeClass("filter-inactive");

      HEPDATA.current_filters[item_parent] = id_parts[1].replace("_", " ");
      $("#clear-" + item_parent).removeClass("hidden");
      HEPDATA.filter_content('', '#hep-submissions');
    });
  };

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
        .attr("class", "row watch-item")
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
      controls.append("button").attr("class", "btn btn-link")
        .append("i").attr("class", "fa fa-eye-slash").attr("title", "Unwatch Record")
        .attr("onclick", function (d) {
          return "dashboard.unwatch('" + d.recid + "')";
        });

    })
  };

  return {
    initialise: function (data) {
      MathJax.Hub.Config({
        tex2jax: {inlineMath: [['$', '$'], ['\\(', '\\)']]}
      });

      MathJax.Hub.Queue(["Typeset", MathJax.Hub]);

      for (var submission_idx in data) {
        HEPDATA.visualization.submission_status.render(data[submission_idx]);
      }

      initialise_list_filter();
      initialise_finalise_btn();
      load_watched_records();

      $(".inspire-btn").bind("click", function () {
        $("#inspire-add-button").attr('data-recid', $(this).attr("data-recid"));
        $("#inspireDialog").modal();
      });

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
    }
  }
})();
