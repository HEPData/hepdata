/**
 * Created by eamonnmaguire on 04/10/2016.
 */

var submissions_vis = (function () {


  var status_colors = d3.scale.ordinal().domain(["todo", "finished", "in progress"]).range(["#e74c3c", "#2ecc71", "#f39c12"]);
  var general_colors = d3.scale.ordinal().range(["#2980b9"]);

  var date_format = "%d %b %Y";

  var formatDate = d3.time.format(date_format);

  var parseDate = function (d) {
    return new Date(d.substring(0, 4),
      d.substring(5, 7),
      d.substring(8));
  };

  var sortByDateAscending = function (a, b) {

    if (typeof a === 'string') {
      var a = d3.time.format(date_format).parse(a);
      var b = d3.time.format(date_format).parse(b);
      return b - a;
    } else {
      return b.last_updated - a.last_updated;
    }

  };

  var calculate_window_width = function () {
    return $(window).width();
  };

  var calculate_vis_width = function (window_width, normal_width_ratio) {
    if (window_width <= 900) {
      return window_width * .63;
    } else {
      return window_width * normal_width_ratio;
    }
  };

  var process_data = function (data) {
    data.forEach(function (d, i) {
      d.index = i;
      d.last_updated = parseDate(d.last_updated);
      d.creation_date = parseDate(d.creation_date);
    });
  };

  function getTops(source_group) {
    return {
      all: function () {
        return source_group.top(10);
      }
    };
  }

  function remove_empty_bins(source_group) {
    return {
      all: function () {
        return source_group.all().filter(function (d) {
          return d.value != 0;
        });
      }
    };
  }

  return {
    render: function (url, options) {
      d3.json(url, function (result) {

        MathJax.Hub.Config({
          tex2jax: {inlineMath: [['$', '$'], ['\\(', '\\)']]}
        });

        var submission_data = result;

        process_data(submission_data);

        var submissions = crossfilter(submission_data),

          submissions_by_date = submissions.dimension(function (d) {
            return d.last_updated;
          }),

          data = submissions.dimension(function (d) {
            return d.data_count;
          }),

          collaboration = submissions.dimension(function (d) {
            return d.collaboration == '' ? 'No collaboration' : d.collaboration;
          }),

          status = submissions.dimension(function (d) {
            return d.status;
          }),

          version = submissions.dimension(function (d) {
            return d.version;
          }),

          submissions_by_date_count_group = submissions_by_date.group(),
          cumulative_count = submissions_by_date.group().reduceSum(),
          collaboration_count_group = collaboration.group(),
          status_count_group = status.group(),
          data_count_group = data.group(),
          version_count_group = version.group();


        var minDate = new Date(submissions_by_date.bottom(1)[0].last_updated);
        var maxDate = new Date(submissions_by_date.top(1)[0].last_updated);

        minDate.setDate(minDate.getDate() - 1);
        maxDate.setDate(maxDate.getDate() + 1);


        var window_width = calculate_window_width();


        var submission_chart = dc.barChart("#submission_vis")
          .width(calculate_vis_width(window_width, 0.65))
          .x(d3.time.scale().domain([minDate, maxDate]))
          .dimension(submissions_by_date, 'Submissions')
          .group(submissions_by_date_count_group)
          .colors(general_colors);

        // submission_chart.on("preRedraw", function (chart) {
        //   var group = chart.group();
        //   var new_group = {
        //     all: function () {
        //       return group.all().filter(function (d) {
        //         return d.value != 0;
        //       })
        //     }
        //   };
        //   chart.group(new_group);
        // });
        //
        // submission_chart.elasticX(true);

        var collaboration_chart = dc.rowChart("#collaboration_vis")
          .width(calculate_vis_width(window_width, 0.3))
          .height(300)
          .dimension(collaboration, 'collaborations')
          .group(getTops(collaboration_count_group))
          .colors(general_colors);


        var status_chart = dc.pieChart("#status_vis")
          .width(calculate_vis_width(window_width, 0.3))
          .dimension(status, 'status')
          .group(status_count_group)
          .colors(status_colors);

        var version_chart = dc.pieChart("#version_vis")
          .width(calculate_vis_width(window_width, 0.3))
          .dimension(version, 'versions')
          .group(version_count_group)
          .colors(general_colors);

        var data_count = dc.barChart("#data_count_vis")
          .width(calculate_vis_width(window_width, 0.3))
          .x(d3.scale.linear().domain([0, 45]))
          .dimension(data, 'data')
          .group(data_count_group)
          .colors(general_colors);

        var detailTable = dc.dataTable('.dc-data-table');
        detailTable.dimension(submissions_by_date)
          .group(function (d) {
            return formatDate(d.last_updated);
          })
          .size(100)
          .columns([
            function () {
              return ""
            },
            function (d) {
              return d.inspire_id;
            },

            function (d) {
              return '<a href="/record/ins' + d.inspire_id + '" target="_blank">' + d.title + '</a>';
            },

            function (d) {
              return d.version;
            },

            function (d) {
              return d.data_count;
            },

            function (d) {
              return d.status;
            },
            function (d) {
              return '<a href="/search/?q=&collaboration=' + d.collaboration + '" target="_blank">' + d.collaboration + '</a>';
            }
          ]).sortBy(function (d) {
          return d.last_updated;
        })
          .order(sortByDateAscending);

        detailTable.on("redraw", function (chart) {
          alert("filtered");
          MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
        });

        dc.renderAll();
      });
    }
  }


})();
