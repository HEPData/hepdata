import $ from 'jquery'
import HEPDATA from './hepdata_common.js'
import './hepdata_reviews.js'

$(document).ready(function() {

  $(".manage-review-menu li").on('click', function () {
      var active_target = $(this).attr('data-screen-target');
      window.active_target = active_target;
      $(".manage-review-menu li").each(function () {
          var current_target = $(this).attr('data-screen-target');
          $("#" + $(this).attr('data-screen-target')).toggleClass("hidden", current_target != active_target);
          $(this).toggleClass("active", current_target == active_target);
      });
      hide_pane("#confirmation");
      hide_pane("#add_pane");
  });

  $(document).on('click', '.add-new-uprev', function () {
      $("#add_pane").removeClass("hidden");

      var type = this.id.split('_')[1];

      $("#add_type").html(type);
      $("#type").val(type);
      if (window.active_target == undefined) {
          window.active_target = 'uploaders_reviewers';
      }

      $(".manage-review-menu li").each(function () {
          $("#" + $(this).attr('data-screen-target')).addClass("hidden");
      });
  });

  $(document).on('click', '.mail-trigger', function () {
      window.recid = $(this).attr('data-recid');
      window.action = $(this).attr('data-action');
      window.userid = $(this).attr('data-userid');
      window.data_person_type = $(this).attr('data-person-type');

      var confirmation_html = '<p>Are you sure you want to ' + window.action + ' this ' + window.data_person_type + 'er?</p>';
      if (window.action == 'promote') {
        confirmation_html += '<p>This action will send an email immediately to invite the user to join the ' + window.data_person_type + ' process.</p>';
      }
      show_confirmation(confirmation_html);
  });

  $(document).on('click', '.confirm-move-action', function () {
      $.ajax({
          dataType: "json",
          url: '/permissions/manage/' + window.recid + '/' + window.data_person_type + '/' + window.action + '/' + window.userid,
          type: 'POST',
          data: {
              review_message: $("#review-message").val()
          },
          success: function (data) {
              if (data.success) {
                  process_reviews(data['recid']);
                  hide_pane("#confirmation");
              } else {
                  alert("Error! " + data.message)
              }
          }
      })
  });

  $(document).on('click', '.confirm-add-user-action', function (event) {

      event.stopImmediatePropagation();

      var name = $('#name').val();
      var email = $('#email').val();
      var type = $('#type').val();

      $.ajax({
          dataType: "json",
          url: '/permissions/manage/person/add/' + window.recid,
          type: 'post',
          data: {'name': name, 'email': email, 'type': type},
          success: function (data) {
              if (data.success) {
                  process_reviews(data['recid']);
                  hide_pane("#add_pane");
              } else {
                  alert("Error! " + data.message)
              }
          }
      })
  });

  $(document).on('click', '.reject-move-action', function (event) {
      event.stopImmediatePropagation();
      hide_pane("#confirmation");
  });

  $(document).on('click', '.reject-add-user-action', function (event) {
      event.stopImmediatePropagation();
      hide_pane("#add_pane");
  });


  function show_confirmation(message) {
      $("#confirmation_message").html(message);
      $("#confirmation").removeClass("hidden");

      if (window.active_target == undefined) {
          window.active_target = 'uploaders_reviewers';
      }

      $(".manage-review-menu li").each(function () {
          $("#" + $(this).attr('data-screen-target')).addClass("hidden");
      });
  }

  function hide_pane(pane_id) {
      $("#" + window.active_target).removeClass("hidden");
      $(pane_id).addClass("hidden");
  }

  function process_reviews(recid) {

      $.ajax({
          dataType: "json",
          url: '/record/coordinator/view/' + recid,
          processData: false,
          cache: true,
          success: function (data) {
              var primary_reviewers = data['primary-reviewers'];
              var primary_uploaders = data['primary-uploaders'];
              var reserve_reviewers = data['reserve-reviewers'];
              var reserve_uploaders = data['reserve-uploaders'];

              function create_section_contents(placement, array, type, additional_class) {
                  // reset html
                  $(placement).html('');
                  if (array.length > 0) {
                      for (var val_idx in array) {
                          var html_block = '<div class="' + type + ' ' + additional_class + '">';
                          html_block += '<div class="info">' + array[val_idx]['full_name'] + '<br/><span class="review-email">' + array[val_idx]['email'] + '</span></div>';
                          var icon = array[val_idx]['accepted'] ? 'check' : 'times';
                          html_block += '<div class="recent-activity"><span>Accepted?</span><br/><span class="fa fa-' + icon + '"></span></div>';
                          html_block += '<div class="recent-activity"><span>Last action</span><br/><span class="' + array[val_idx]['last_action_status'] + '">' + array[val_idx]['last_action'] + '</span></div>';

                          var arrow_box_class = additional_class == 'primary' ? 'danger' : 'success';
                          var alt_text = additional_class == 'primary' ? 'Demote user to reserve ' + type : 'Promote user to primary ' + type;
                          var arrow_box_icon = additional_class == 'primary' ? 'fa-chevron-down' : 'fa-chevron-up';
                          var action_type = (type == 'reviewer') ? 'review' : 'upload';
                          var downgrade_show = (data['reserve-' + type + 's'].length == 0 && data['primary-' + type + 's'].length == 0) ? "hidden" : (data['primary-' + type + 's'].length > 1) ? "" : (data['reserve-' + type + 's'].length > 0) ? "" : "hidden";
                          var action = additional_class == 'primary' ? "demote" : "promote";

                          html_block += '<div class="trigger-actions">';
                          if (additional_class == 'reserve') {
                            html_block += '<button data-toggle="tooltip" data-placement="top" title="Remove user from submission" class="btn btn-xs btn-danger mail-trigger" data-action="remove" data-person-type="' + action_type + '" data-recid="' + data["recid"] + '" data-userid="' + array[val_idx]['id'] + '"><span class="fa fa-trash-o"></span> </button>';
                          } else {
                            html_block += '<button data-toggle="tooltip" data-placement="top" title="Send a reminder to this user" class="btn btn-xs btn-primary mail-trigger" data-action="email" data-person-type="' + action_type + '" data-recid="' + data["recid"] + '" data-userid="' + array[val_idx]['id'] + '"><span class="fa fa-envelope-o"></span> </button>';
                          }
                          html_block += '<button data-toggle="tooltip" data-placement="top" title="' + alt_text + '" class="btn btn-xs btn-' + arrow_box_class + ' ' + downgrade_show + ' mail-trigger" data-action="' + action + '" data-person-type="' + action_type + '" data-recid="' + data["recid"] + '" data-userid="' + array[val_idx]['id'] + '"><span class="fa ' + arrow_box_icon + '"></span> </button>' +
                            '</div>';
                          html_block += '</div>';

                          html_block += '<div class="clearfix"></div>';

                          $(placement).append(html_block)
                      }
                  } else {
                      $(placement).html('<p class="no-entries">No ' + additional_class + ' ' + type + '</p>');
                  }
              }

              create_section_contents("#primary-reviewer", primary_reviewers, 'reviewer', 'primary');
              create_section_contents("#primary-uploader", primary_uploaders, 'uploader', 'primary');
              create_section_contents("#reserve-reviewer", reserve_reviewers, 'reviewer', 'reserve');
              create_section_contents("#reserve-uploader", reserve_uploaders, 'uploader', 'reserve');
              return true;
          }
      });
  }

  function set_observer_key(recid) {
    /**
    * Sets the observer key value on the manage submission dashboard widget.
    *
    * @param {number} recid - The recid to get observer_key for.
    */

    // Call for observer key, with the flag to retrieve
    let observer_promise = HEPDATA.get_observer_key_data(recid, 1);

    observer_promise.then(function(observer_key) {
      if(observer_key) {
        // Unhide container, set value and text on the input
        $('#data_link_container').removeAttr('hidden');
        $('#direct_data_link').val(observer_key);
        $('dashboard_button').attr('data-clipboard-text', observer_key);

        // Attempt to set up the clipboard object for this widget
        HEPDATA.setup_clipboard("#dashboard_button");
      }
    });
  }

  $(document).on('click', '.manage-submission-trigger', function (event) {
      window.recid = $(this).attr('data-recid');
      HEPDATA.load_all_review_messages("#conversation", $(this).attr('data-recid'));
      process_reviews($(this).attr('data-recid'));
      set_observer_key($(this).attr('data-recid'));
  });

  $(document).on('click', '.conversation-trigger', function (event) {
      HEPDATA.load_all_review_messages("#conversation-only", $(this).attr('data-recid'));
  });

  $(document).on('click', '.delete-submission-trigger', function (event) {
      window.recid = $(this).attr('data-recid');
  });

});
