import $ from 'jquery'
import inspire_ds from './inspire.js'

$(document).ready(function () {
  var inspire = false;
  var publication_data = {};
  var default_options = {duration: 300, direction: 'from_right'};


  var toggle_div = function (div_id, options, state, callback) {

      var display = (state == "hide" ? 'none' : 'block');
      if (display !== $(div_id).css('display')) {
          if (state == 'show') $(div_id).css('display', display);

          var animation = {bottom: state == "hide" ? "-=1000px" : "+=1000px"};

          $(div_id).animate(animation, options.duration,
                  function () {
                      if (callback) {
                          callback();
                      }
                      $("#continue_btn").removeClass("hidden");
                      if (state == 'hide') $(div_id).css('display',
                              display);
                  });
      } else {
          if (callback) {
              callback();
              $("#continue_btn").removeClass("hidden");
          }
      }
  };

  var register_key_input_listener = function (input_id, continue_btn_id) {
      $(input_id).on('input', function () {
          if ($(input_id).val().length > 0) {
              $(continue_btn_id).prop('disabled', false);
          } else {
              $(continue_btn_id).prop('disabled', true);

          }
      });
  };

  $("#no_inspire").on('click', function () {
      inspire = false;
      toggle_div("#enter_inspire_id", {duration: 300}, 'hide', function () {
          toggle_div("#enter_title", {duration: 300}, 'show')
      });


  });

  register_key_input_listener("#paper_title", "#continue_btn");


  $("#has_inspire").on('click', function () {
      inspire = true;
      toggle_div("#enter_title", default_options, 'hide', function () {
          toggle_div("#enter_inspire_id", default_options, 'show');
      });

  });

  function change_breadcrumbs(from, to) {
      $(from + " .line").addClass("hidden");
      $(from + " .progress-circle").removeClass("active");

      $(to + " .line").removeClass("hidden");
      $(to + " .progress-circle").addClass("active");
  }

  register_key_input_listener("#inspire_id", "#continue_btn");

  $("#continue_btn").on('click', function () {
      // go to next page.
      if (inspire) {
          var inspire_id = $("#inspire_id").val();

          toggle_div("#inspire_details", default_options, 'hide', function () {
              toggle_div("#inspire_preview", default_options, 'show', function () {
                  inspire_ds.get_inspire_data(inspire_id, render_inspire_preview);
              })
          });

      } else {
          toggle_div("#inspire_details", default_options, 'hide', function () {
              change_breadcrumbs("#progress-inspire", "#progress-people");
              toggle_div("#reviewers_uploaders", default_options, 'show')
          });
      }

  });

  $("#preview_back_btn").on('click', function () {
      toggle_div("#inspire_preview", default_options, 'hide', function () {
          $("#inspire-result").html('<div class="spinner" style="margin-top: 9em">' +
                  '<div class="ball ball-purple"></div>' +
                  '<p class="text-grey">Loading information from Inspire.</p></div>');
          $("#preview_back_btn").addClass("hidden");
          $("#preview_continue_btn").addClass("hidden");
          toggle_div("#inspire_details", default_options, 'show')
      });
  });

  $("#preview_continue_btn").on('click', function () {
      toggle_div("#inspire_preview", default_options, 'hide', function () {
          change_breadcrumbs("#progress-inspire", "#progress-people");
          toggle_div("#reviewers_uploaders", default_options, 'show')
      });
  });

  $("#people_back_btn").on('click', function () {
      var div = inspire ? "#inspire_preview" : "#inspire_details";
      toggle_div("#reviewers_uploaders", default_options, 'hide', function () {
          change_breadcrumbs("#progress-people", "#progress-inspire");
          toggle_div(div, default_options, 'show')
      });
  });


  $("#people_continue_btn").on('click', function () {
      toggle_div("#reviewers_uploaders", default_options, 'hide', function () {
          toggle_div("#uploader_message", default_options, 'show', function () {
              window.MathJax.typeset();
          })
      });
  });


  $("#message_back_btn").on('click', function () {
      toggle_div("#uploader_message", default_options, 'hide', function () {
          toggle_div("#reviewers_uploaders", default_options, 'show')
      });
  });


  $("#message_continue_btn").on('click', function () {
      toggle_div("#uploader_message", default_options, 'hide', function () {
          change_breadcrumbs("#progress-people", "#progress-submit");
          toggle_div("#check", default_options, 'show', function () {
              $("#publication_title").text(inspire ? publication_data.query.title : $("#paper_title").val());
              window.MathJax.typeset();
          })
      });
  });

  $("#submit_back_btn").on('click', function () {

      toggle_div("#check", default_options, 'hide', function () {
          change_breadcrumbs("#progress-submit", "#progress-people");
          toggle_div("#uploader_message", default_options, 'show')
      });
  });

  var render_inspire_preview = function (data) {
      var html = '';

      publication_data = data;

      if (!inspire_ds.is_null(data) && data.status == 'success') {
          $("#inspire-retrieve-progress").addClass("hidden");

          html = "<div class='alert alert-info'><strong>Is this " +
                  "the publication you were looking for?</strong><br/>" +
                  "A preview of the publication (not everything is " +
                  "displayed).</div>" +
                  "<div class='publication-info'>";

          html = inspire_ds.create_html_summary(data, html);
          html += '</div>';

          $("#preview_back_btn").removeClass("hidden");
          $("#preview_continue_btn").removeClass("hidden");


      }
      else if (data.status == 'exists') {
          html = '<div class="alert alert-danger">A ' +
                  '<a href="/record/ins' + data.id + '" target="_blank">' +
                  'record</a> with this Inspire ID already exists in HEPData.' +
                  '</div>';
          html = inspire_ds.create_html_summary(data, html);

          $("#preview_back_btn").removeClass("hidden");
          $("#preview_continue_btn").addClass("hidden");
      } else {
          html = '<div class="alert alert-danger">An error occurred while trying to find the Inspire record.</div>';
          $("#preview_back_btn").removeClass("hidden");
          $("#preview_continue_btn").addClass("hidden");
      }

      $("#inspire-result").html(html);
      window.MathJax.typeset();
  };

  $("#submit_btn").on('click', function () {

      var payload = {};

      payload['inspire_id'] = inspire ? $("#inspire_id").val() : null;
      payload['title'] = inspire ? null : $("#paper_title").val();
      payload['message'] = $("#uploader-message-input").val();
      payload['reviewer'] = $('#reviewer_name').val() + "::" + $('#reviewer_email').val();
      payload['uploader'] = $('#uploader_name').val() + "::" + $('#uploader_email').val();

      var progress_html = '  <i class="fa fa-refresh fa-spin" style="font-size: 5.3em; color: #894B9D; padding-bottom: .4em"></i><br/>' +
              '<p style="font-size: 1.3em">Processing Submission. This won\'t take long.</p>';
      $("#submission_state").html(progress_html);

      $("#submit_back_btn").addClass("hidden");
      $("#submit_btn").addClass("hidden");

      $.ajax({
          url: '/submit',
          data: payload,
          method: 'POST',
          success: function () {
              var finished_html = '<i class="fa fa-check-circle" style="font-size: 5.3em; color: #894B9D; padding-bottom: .4em"></i><br/>' +
                      '<p style="font-size: 1.3em">Submission Complete!</p>';
              $("#submission_state").html(finished_html);
              $("#another_submission").removeClass("hidden");

          }
      })
  })
});
