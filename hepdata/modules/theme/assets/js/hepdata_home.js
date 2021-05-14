import $ from 'jquery'
import 'bootstrap'

$(document).ready(function () {
  $.ajax({
      url: '/record/latest?n=3',
      method: 'GET',
      success: function (data) {
          data = data['latest'];
          for (var record in data) {

              var record_html_block = '<div class="latest-record col-md-4 col-xs-12" id="ins' + data[record]['inspire_id'] + '">';

              if (data[record]['version'] > 1) {
                  record_html_block += ' <div class="version"><i class="fa fa-code-fork"></i> Version ' + data[record]['version'] + '</div>';
              }
              record_html_block += '<a href="/record/ins' + data[record]['inspire_id'] + '" class="title">' + data[record]['title'] + '</a><br/><br/>';


              if (data[record]['collaborations'].length > 0) {
                  record_html_block += 'The ';
                  for (var collaboration in data[record]['collaborations']) {
                      if (collaboration > 0) {
                        record_html_block += '&';
                      }
                      record_html_block += ' <a href="/search?q=&collaboration=' + data[record]['collaborations'][collaboration] + '" class="collaboration">' + data[record]['collaborations'][collaboration] + '</a> ';
                  }
                  record_html_block += 'collaboration' + (data[record]['collaborations'].length > 1 ? 's' : '');
              } else if (data[record]['first_author']) {

                  record_html_block += '<a href="/search/?q=&author=' + data[record]['first_author']['full_name'] + '" class="author">' + data[record]['first_author']['full_name'];
                  if (data[record]['author_count'] > 1) {
                      record_html_block += ' <i>et al</i>';
                  }
                  record_html_block += ' </a>';
              }


              record_html_block += '<br/>';

              record_html_block += "<br/>";

              if (data[record]['journal_info'])
                  record_html_block += '<span class="journal"> ' + data[record]['journal_info'] + '</span><br/>';

              record_html_block += "<br/>";

              record_html_block += '<div class="date"><i class="fa fa-clock-o"></i>  Updated ' + data[record]['last_updated'] + '</div>';

              if (data[record]['creation_date'] != null) {
                  record_html_block += '<div class="date"><i class="fa fa-bookmark-o"></i> Published on ' + data[record]['creation_date'] + '</div>';
              }

              record_html_block += '</div>';

              $("#latest_records").append(record_html_block);
          }

          $(window).on('load', function() {
            window.MathJax.typeset();
          });
      }
  });

  $.ajax({
      url: '/record/count',
      method: 'GET',
      success: function (data) {
          $("#record_stats").html('<a href="/search">Search on <span style="font-weight: bolder">' + data["publications"] + '</span> publications and <span style="font-weight: bolder">' + data["data"] + '</span> data tables.</a>')
      }
  });
});
